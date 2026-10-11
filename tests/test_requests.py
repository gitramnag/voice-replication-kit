from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from voice_replication_kit.requests import (
    build_requests,
    request_identity,
    validate_document,
    validate_private_profile,
    validate_request,
)
from voice_replication_kit.text import apply_pronunciation_overrides, prepare_for_speech


ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"


def _profile() -> dict:
    return {
        "schema_version": 1,
        "model": "cosyvoice3",
        "recipes": {
            "narration_neutral": {
                "reference_file": "refs/neutral-reference.wav",
                "reference_text": "A private transcript stays in the private profile.",
                "reference_sha256": "0" * 64,
                "seed": 4242,
                "text_shape": "connected_sentence",
            },
            "warm_friendly": {
                "reference_file": "refs/warm-reference.wav",
                "reference_text": "Another private transcript remains outside Git.",
                "reference_sha256": "1" * 64,
                "seed": 1701,
                "text_shape": "two_sentences",
            },
        },
    }


def _document() -> dict:
    return {
        "schema_version": 1,
        "title": "Generic product tour",
        "language": "en",
        "segments": [
            {
                "id": "opening",
                "intent": "A serious warning",
                "style": "warm_friendly",
                "text": "SQL is ready. PostgreSQL remains available. Welcome aboard.",
                "pronunciation_overrides": {"SQL": "sequel"},
            }
        ],
    }


def _complete_request() -> dict:
    reference_text = "A private transcript stays in the private profile."
    row = {
        "schema_version": 1,
        "prompt_id": "production_opening",
        "source_segment_id": "opening",
        "unit_index": 1,
        "style": "narration_neutral",
        "language": "en",
        "text": "This is a prepared render unit.",
        "seed": 4242,
        "reference_file": "refs/neutral-reference.wav",
        "reference_text": reference_text,
        "reference_sha256": "0" * 64,
        "reference_text_sha256": hashlib.sha256(reference_text.encode("utf-8")).hexdigest(),
        "text_shape": "connected_sentence",
        "model_revision": MODEL_REVISION,
        "pronunciation_overrides": {},
    }
    row["request_id"] = request_identity(row)
    return row


@pytest.mark.parametrize(
    "reference_file",
    ["../reference.wav", "refs/../../reference.wav", "/tmp/reference.wav", r"refs\reference.wav"],
)
def test_private_profile_rejects_reference_path_escape(reference_file: str) -> None:
    profile = _profile()
    profile["recipes"]["narration_neutral"]["reference_file"] = reference_file

    with pytest.raises(ValueError, match="reference_file"):
        validate_private_profile(profile)


def test_document_schema_rejects_duplicate_or_empty_segments() -> None:
    document = _document()
    document["segments"].append(deepcopy(document["segments"][0]))

    with pytest.raises(ValueError, match="unique"):
        validate_document(document)

    document["segments"] = []
    with pytest.raises(ValueError, match="non-empty"):
        validate_document(document)


def test_private_objects_reject_unknown_fields() -> None:
    profile = dict(_profile(), evaluator_name="private")
    with pytest.raises(ValueError, match="unexpected"):
        validate_private_profile(profile)

    document = dict(_document(), unexpected_document_field="must not pass")
    with pytest.raises(ValueError, match="unexpected"):
        validate_document(document)

    request = build_requests(_document(), _profile(), MODEL_REVISION)[0]
    request["unexpected_private_field"] = "must not pass"
    with pytest.raises(ValueError, match="unexpected"):
        validate_request(request)


@pytest.mark.parametrize("version", [0, 2, "1", None])
def test_private_objects_reject_schema_versions_other_than_one(version: object) -> None:
    profile = _profile()
    profile["schema_version"] = version
    with pytest.raises(ValueError, match="schema_version 1"):
        validate_private_profile(profile)

    document = _document()
    document["schema_version"] = version
    with pytest.raises(ValueError, match="schema_version must be 1"):
        validate_document(document)

    request = _complete_request()
    request["schema_version"] = version
    with pytest.raises(ValueError, match="schema_version must be 1"):
        validate_request(request)


def test_private_profile_rejects_boolean_schema_version() -> None:
    profile = _profile()
    profile["schema_version"] = True

    with pytest.raises(ValueError, match="schema_version 1"):
        validate_private_profile(profile)


def test_production_document_rejects_boolean_schema_version() -> None:
    document = _document()
    document["schema_version"] = True

    with pytest.raises(ValueError, match="schema_version must be 1"):
        validate_document(document)


def test_materialized_request_rejects_boolean_schema_version() -> None:
    request = _complete_request()
    request["schema_version"] = True

    with pytest.raises(ValueError, match="schema_version must be 1"):
        validate_request(request)


@pytest.mark.parametrize(
    "reference_file",
    ["refs/neutral reference.wav", "refs/neutral-reference.WAV"],
)
def test_reference_file_runtime_validation_matches_public_schemas(
    reference_file: str,
) -> None:
    profile_schema = json.loads(
        (ROOT / "configs" / "schemas" / "private-profile.schema.json").read_text(
            encoding="utf-8"
        )
    )
    request_schema = json.loads(
        (ROOT / "configs" / "schemas" / "request.schema.json").read_text(
            encoding="utf-8"
        )
    )
    profile = _profile()
    profile["recipes"]["narration_neutral"]["reference_file"] = reference_file
    request = _complete_request()
    request["reference_file"] = reference_file

    with pytest.raises(ValueError, match="reference_file"):
        validate_private_profile(profile)
    with pytest.raises(ValueError, match="reference_file"):
        validate_request(request)
    assert list(Draft202012Validator(profile_schema).iter_errors(profile))
    assert list(Draft202012Validator(request_schema).iter_errors(request))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("unit_index", 0, "unit_index"),
        ("text", "x" * 221, "220"),
        ("request_id", "opening_u01_deadbeef__s9", "seed suffix"),
        ("pronunciation_overrides", {"SQL": ""}, "non-empty"),
    ],
)
def test_materialized_request_validation_matches_public_schema(
    field: str, value: object, message: str
) -> None:
    request = build_requests(_document(), _profile(), MODEL_REVISION)[0]
    request[field] = value

    with pytest.raises(ValueError, match=message):
        validate_request(request)


def test_request_ids_are_stable_and_derived_from_the_render_unit() -> None:
    profile = _profile()
    document = _document()

    first = build_requests(document, profile, MODEL_REVISION)
    renamed = deepcopy(document)
    renamed["title"] = "A renamed document"
    second = build_requests(renamed, profile, MODEL_REVISION)

    assert first == second
    assert [row["unit_index"] for row in first] == [1, 2]
    assert all(row["request_id"].endswith("__s1701") for row in first)

    changed = deepcopy(document)
    changed["segments"][0]["text"] += " One more sentence."
    assert [row["request_id"] for row in build_requests(changed, profile, MODEL_REVISION)] != [
        row["request_id"] for row in first
    ]


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("reference_sha256", "2" * 64),
        ("reference_text", "A different exact private transcript."),
        ("reference_text_sha256", "3" * 64),
        ("seed", 1701),
        ("text_shape", "short_clause"),
        ("model_revision", "0123456789abcdef0123456789abcdef01234567"),
        ("text", "This is a different prepared render unit."),
    ],
)
def test_request_identity_changes_for_every_render_input(
    field: str, replacement: object
) -> None:
    row = _complete_request()
    changed = dict(row, **{field: replacement})

    assert request_identity(row) != request_identity(changed)


def test_different_references_never_share_a_request_id() -> None:
    first_profile = _profile()
    second_profile = deepcopy(first_profile)
    second_profile["recipes"]["warm_friendly"].update(
        reference_file="refs/alternate-reference.wav",
        reference_text="A different exact private transcript.",
        reference_sha256="2" * 64,
    )

    first = build_requests(_document(), first_profile, MODEL_REVISION)
    second = build_requests(_document(), second_profile, MODEL_REVISION)

    assert {row["request_id"] for row in first}.isdisjoint(
        row["request_id"] for row in second
    )


def test_request_rejects_a_stale_reference_transcript_digest() -> None:
    request = _complete_request()
    request["reference_text"] = "A changed transcript with a stale stored digest."

    with pytest.raises(ValueError, match="reference_text_sha256"):
        validate_request(request)


def test_explicit_style_and_pronunciation_override_are_preserved() -> None:
    rows = build_requests(_document(), _profile(), MODEL_REVISION)

    assert {row["style"] for row in rows} == {"warm_friendly"}
    assert rows[0]["text"] == "sequel is ready. PostgreSQL remains available."
    assert rows[1]["text"] == "Welcome aboard."
    assert rows[0]["pronunciation_overrides"] == {"SQL": "sequel"}
    expected_digest = hashlib.sha256(
        _profile()["recipes"]["warm_friendly"]["reference_text"].encode("utf-8")
    ).hexdigest()
    assert {row["reference_text_sha256"] for row in rows} == {expected_digest}
    assert {row["model_revision"] for row in rows} == {MODEL_REVISION}


def test_short_clause_shape_splits_at_declared_clause_boundaries() -> None:
    document = _document()
    document["segments"][0]["text"] = (
        "First synthetic clause, second clause; third clause: fourth clause."
    )
    profile = _profile()
    profile["recipes"]["warm_friendly"]["text_shape"] = "short_clause"
    profile_schema = json.loads(
        (ROOT / "configs" / "schemas" / "private-profile.schema.json").read_text(
            encoding="utf-8"
        )
    )

    rows = build_requests(document, profile, MODEL_REVISION)

    assert list(Draft202012Validator(profile_schema).iter_errors(profile)) == []
    assert [row["text"] for row in rows] == [
        "First synthetic clause,",
        "second clause;",
        "third clause:",
        "fourth clause.",
    ]
    assert all(row["text_shape"] == "short_clause" for row in rows)


def test_evaluation_reference_key_is_optional_without_weakening_candidate_group() -> None:
    request = _complete_request()
    request["reference_key"] = "synthetic-ref"
    validate_request(request)

    request["candidate_of"] = request["request_id"]
    with pytest.raises(ValueError, match="supplied together"):
        validate_request(request)


def test_pronunciation_overrides_are_whole_word_and_require_values() -> None:
    assert (
        apply_pronunciation_overrides("SQL and PostgreSQL", {"SQL": "sequel"})
        == "sequel and PostgreSQL"
    )
    with pytest.raises(ValueError, match="non-empty"):
        apply_pronunciation_overrides("SQL", {"SQL": ""})


def test_long_sentences_are_chunked_without_losing_words() -> None:
    text = " ".join(f"word{index}" for index in range(1, 51)) + "."

    chunks = prepare_for_speech(text, max_characters=60)

    assert len(chunks) > 1
    assert all(len(chunk) <= 60 for chunk in chunks)
    assert " ".join(chunks).replace(" .", ".") == text


def test_public_json_schemas_match_the_private_objects_built_by_code() -> None:
    profile_schema = json.loads(
        (ROOT / "configs" / "schemas" / "private-profile.schema.json").read_text(
            encoding="utf-8"
        )
    )
    request_schema = json.loads(
        (ROOT / "configs" / "schemas" / "request.schema.json").read_text(
            encoding="utf-8"
        )
    )
    document_schema = json.loads(
        (ROOT / "configs" / "schemas" / "production-document.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(profile_schema)
    Draft202012Validator.check_schema(request_schema)
    Draft202012Validator.check_schema(document_schema)

    assert list(Draft202012Validator(profile_schema).iter_errors(_profile())) == []
    assert list(Draft202012Validator(document_schema).iter_errors(_document())) == []
    rows = build_requests(_document(), _profile(), MODEL_REVISION)
    assert all(
        list(Draft202012Validator(request_schema).iter_errors(row)) == []
        for row in rows
    )

    invalid = dict(rows[0], unexpected_private_field="must not pass")
    assert list(Draft202012Validator(request_schema).iter_errors(invalid))
