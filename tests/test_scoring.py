from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from voice_replication_kit.scoring import (
    REQUIRED_METRICS,
    build_blind_map,
    build_blind_pack,
    summarize_scores,
)
from voice_replication_kit.requests import request_identity, validate_request


ROOT = Path(__file__).resolve().parents[1]


def _row(label: str, style: str, score: int | None) -> dict:
    row = {
        "blind_label": label,
        "style": style,
        "notes": "",
    }
    row.update({metric: score for metric in REQUIRED_METRICS})
    return row


def test_blind_labels_are_deterministic_and_input_order_independent() -> None:
    requests = [
        {"request_id": "neutral_u01_alpha__s1"},
        {"request_id": "neutral_u01_beta__s2"},
        {"request_id": "neutral_u01_gamma__s3"},
    ]

    first = build_blind_map(requests)
    second = build_blind_map(list(reversed(requests)))

    assert first == second
    assert set(first) == {row["request_id"] for row in requests}
    assert sorted(first.values()) == ["CLIP-001", "CLIP-002", "CLIP-003"]


def test_blind_labels_reject_duplicate_request_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        build_blind_map([{"request_id": "same"}, {"request_id": "same"}])


def _candidate(source_segment_id: str, prompt_id: str, seed: int) -> dict:
    reference_text = "A private synthetic transcript."
    row = {
        "schema_version": 1,
        "prompt_id": prompt_id,
        "source_segment_id": source_segment_id,
        "unit_index": 1,
        "style": "narration_neutral",
        "language": "en",
        "text": "A private synthetic prompt.",
        "text_shape": "connected_sentence",
        "seed": seed,
        "reference_key": "private-ref",
        "reference_file": "refs/private-ref.wav",
        "reference_text": reference_text,
        "reference_sha256": "a" * 64,
        "reference_text_sha256": hashlib.sha256(
            reference_text.encode("utf-8")
        ).hexdigest(),
        "model_revision": "c" * 40,
        "pronunciation_overrides": {},
    }
    row["request_id"] = request_identity(row)
    return row


def test_blind_pack_is_stable_and_exposes_only_evaluator_fields() -> None:
    rows = [
        _candidate("synthetic-b", "prompt-b", 4242),
        _candidate("synthetic-a", "prompt-a", 1087),
    ]

    visible, secret = build_blind_pack(rows)
    reversed_visible, reversed_secret = build_blind_pack(list(reversed(rows)))

    assert visible == reversed_visible
    assert secret == reversed_secret
    ordered_ids = sorted(row["request_id"] for row in rows)
    assert secret == {"V001": ordered_ids[0], "V002": ordered_ids[1]}
    assert [row["blind_label"] for row in visible] == ["V001", "V002"]
    assert all(
        set(row)
        == {
            "blind_label",
            "prompt_id",
            "source_segment_id",
            "unit_index",
            "style",
            "language",
            "text_shape",
            "candidate_audio_basename",
        }
        for row in visible
    )
    assert [row["candidate_audio_basename"] for row in visible] == [
        "V001.wav",
        "V002.wav",
    ]
    serialized = json.dumps(visible)
    private_row = rows[0]
    for private_value in (
        *ordered_ids,
        private_row["reference_key"],
        private_row["reference_file"],
        private_row["reference_text"],
        private_row["reference_sha256"],
        private_row["reference_text_sha256"],
        private_row["model_revision"],
        str(private_row["seed"]),
    ):
        assert private_value not in serialized


def test_blind_pack_rejects_a_forced_blind_label_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "voice_replication_kit.scoring._blind_label",
        lambda _index: "V001",
    )
    rows = [
        _candidate("synthetic-b", "prompt-b", 4242),
        _candidate("synthetic-a", "prompt-a", 1087),
    ]

    with pytest.raises(ValueError, match="blind labels must be unique"):
        build_blind_pack(rows)


def test_blind_pack_rejects_duplicate_request_ids() -> None:
    row = _candidate("same", "prompt-a", 1)

    with pytest.raises(ValueError, match="unique"):
        build_blind_pack([row, dict(row)])


def test_blind_pack_rejects_a_noncanonical_matrix_request() -> None:
    row = _candidate("synthetic-a", "prompt-a", 1087)
    row["seed"] = 4242

    with pytest.raises(ValueError, match="request_id seed suffix"):
        build_blind_pack([row])


def test_reference_key_type_matches_schema_at_request_and_blind_boundaries() -> None:
    row = _candidate("synthetic-a", "prompt-a", 1087)
    row["reference_key"] = 123
    schema = json.loads(
        (ROOT / "configs" / "schemas" / "request.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert list(Draft202012Validator(schema).iter_errors(row))
    with pytest.raises(ValueError, match="reference_key"):
        validate_request(row)
    with pytest.raises(ValueError, match="reference_key"):
        build_blind_pack([row])


def test_incomplete_ratings_never_select_a_winner() -> None:
    rows = [
        _row("CLIP-001", "narration_neutral", 5),
        _row("CLIP-002", "narration_neutral", None),
    ]

    summary = summarize_scores(rows)
    neutral = summary["styles"]["narration_neutral"]

    assert summary["complete"] is False
    assert neutral == {
        "candidate_count": 2,
        "rated_candidate_count": 1,
        "complete": False,
        "best_score": None,
        "winner": None,
        "tied_labels": [],
    }


def test_ties_are_reported_without_selecting_a_winner() -> None:
    rows = [
        _row("CLIP-010", "warm_friendly", 4),
        _row("CLIP-011", "warm_friendly", 4),
    ]

    summary = summarize_scores(rows)["styles"]["warm_friendly"]

    assert summary["complete"] is True
    assert summary["best_score"] == 4.0
    assert summary["winner"] is None
    assert summary["tied_labels"] == ["CLIP-010", "CLIP-011"]


def test_scores_are_summarized_independently_by_style() -> None:
    rows = [
        _row("CLIP-020", "narration_neutral", 3),
        _row("CLIP-021", "narration_neutral", 5),
        _row("CLIP-030", "serious_authoritative", 4),
    ]

    summary = summarize_scores(rows)

    assert summary["complete"] is True
    assert summary["styles"]["narration_neutral"]["winner"] == "CLIP-021"
    assert summary["styles"]["serious_authoritative"]["winner"] == "CLIP-030"


@pytest.mark.parametrize("field", ["evaluator", "evaluator_name", "reviewer"])
def test_personal_evaluator_identity_fields_are_rejected(field: str) -> None:
    row = _row("CLIP-040", "narration_neutral", 4)
    row[field] = "private identity"

    with pytest.raises(ValueError, match="identity"):
        summarize_scores([row])


def test_public_scorecard_schema_and_blank_decisions_contain_no_identity_fields() -> None:
    schema = json.loads(
        (ROOT / "evaluation" / "schemas" / "scorecard.schema.json").read_text(
            encoding="utf-8"
        )
    )
    blank = json.loads(
        (ROOT / "evaluation" / "examples" / "blank-decisions.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    assert list(Draft202012Validator(schema).iter_errors(blank)) == []

    serialized = json.dumps({"schema": schema, "blank": blank}).lower()
    assert "evaluator" not in serialized
    assert "reviewer" not in serialized
    assert len(blank["decisions"]) == 14
    assert all(item["selected_blind_label"] is None for item in blank["decisions"])
