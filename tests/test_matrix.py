from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from voice_replication_kit.matrix import (
    build_evaluation_matrix,
    expand_candidates,
    next_output_path,
    resolve_reference_path,
    write_jsonl_immutable,
)
from voice_replication_kit.requests import request_identity, validate_request


ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"


def _evaluation_plan(
    *,
    reference_keys: tuple[str, ...] = ("ref-a",),
    seeds: tuple[int, ...] = (1087,),
    text_shapes: tuple[str, ...] = ("connected_sentence",),
) -> dict:
    return {
        "schema_version": 1,
        "experiment_question": "Which synthetic candidate is clearest?",
        "prompts": [
            {
                "prompt_id": "synthetic_prompt_01",
                "source_segment_id": "synthetic-segment",
                "unit_index": 1,
                "style": "narration_neutral",
                "language": "en",
                "text": "This sentence contains no real person's words.",
                "pronunciation_overrides": {},
            }
        ],
        "references": [
            {
                "reference_key": key,
                "reference_file": f"refs/{key}.wav",
                "reference_text": f"Synthetic transcript for {key}.",
                "reference_sha256": hashlib.sha256(
                    f"synthetic audio for {key}".encode("utf-8")
                ).hexdigest(),
            }
            for key in reference_keys
        ],
        "seeds": list(seeds),
        "text_shapes": list(text_shapes),
    }


def _request(seed: int = 4242) -> dict:
    request = {
        "schema_version": 1,
        "prompt_id": "production_opening_01",
        "source_segment_id": "opening",
        "unit_index": 1,
        "style": "narration_neutral",
        "language": "en",
        "text": "This is a generic sentence.",
        "seed": seed,
        "reference_file": "refs/neutral-reference.wav",
        "reference_text": "The private transcript travels only with the private request pack.",
        "reference_sha256": "0" * 64,
        "reference_text_sha256": hashlib.sha256(
            b"The private transcript travels only with the private request pack."
        ).hexdigest(),
        "text_shape": "connected_sentence",
        "model_revision": "29e01c4e8d000f4bcd70751be16fa94bf3d85a18",
        "pronunciation_overrides": {},
    }
    request["request_id"] = request_identity(request)
    return request


def test_matrix_contains_every_reference_seed_and_shape() -> None:
    plan = _evaluation_plan(
        reference_keys=("ref-a", "ref-b"),
        seeds=(1087, 1701, 4242),
        text_shapes=("short_clause", "connected_sentence"),
    )

    rows = build_evaluation_matrix(plan, MODEL_REVISION)

    observed = {
        (row["reference_key"], row["seed"], row["text_shape"])
        for row in rows
    }
    assert observed == set(
        itertools.product(
            ["ref-a", "ref-b"],
            [1087, 1701, 4242],
            ["short_clause", "connected_sentence"],
        )
    )
    assert len(rows) == 12
    assert len({row["request_id"] for row in rows}) == 12
    assert [row["request_id"] for row in rows] == sorted(
        row["request_id"] for row in rows
    )


def test_every_matrix_row_is_a_canonical_request_including_short_clause() -> None:
    plan = _evaluation_plan(
        text_shapes=("short_clause", "connected_sentence", "two_sentences")
    )
    request_schema = json.loads(
        (ROOT / "configs" / "schemas" / "request.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(request_schema)

    rows = build_evaluation_matrix(plan, MODEL_REVISION)

    assert {row["text_shape"] for row in rows} == {
        "short_clause",
        "connected_sentence",
        "two_sentences",
    }
    for row in rows:
        validate_request(row)
        assert list(validator.iter_errors(row)) == []


@pytest.mark.parametrize("dimension", ["prompts", "references", "seeds", "text_shapes"])
def test_evaluation_matrix_rejects_an_empty_dimension(dimension: str) -> None:
    plan = _evaluation_plan()
    plan[dimension] = []

    with pytest.raises(ValueError, match=dimension):
        build_evaluation_matrix(plan, MODEL_REVISION)


@pytest.mark.parametrize(
    ("dimension", "key"),
    [("prompts", "prompt_id"), ("references", "reference_key")],
)
def test_evaluation_matrix_rejects_duplicate_source_keys(
    dimension: str, key: str
) -> None:
    plan = _evaluation_plan()
    duplicate = deepcopy(plan[dimension][0])
    plan[dimension].append(duplicate)

    with pytest.raises(ValueError, match=key):
        build_evaluation_matrix(plan, MODEL_REVISION)


def test_evaluation_matrix_rejects_duplicate_output_request_ids() -> None:
    plan = _evaluation_plan()
    duplicate_identity = deepcopy(plan["prompts"][0])
    duplicate_identity["prompt_id"] = "synthetic_prompt_02"
    plan["prompts"].append(duplicate_identity)

    with pytest.raises(ValueError, match="request ids must be unique"):
        build_evaluation_matrix(plan, MODEL_REVISION)


def test_evaluation_plan_schema_matches_the_runtime_contract() -> None:
    schema = json.loads(
        (ROOT / "configs" / "schemas" / "evaluation-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema)
    Draft202012Validator.check_schema(schema)

    assert list(validator.iter_errors(_evaluation_plan())) == []
    invalid = dict(_evaluation_plan(), unexpected_private_field="must not pass")
    assert list(validator.iter_errors(invalid))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_segment_id", "   "),
        ("language", "  "),
        ("pronunciation_overrides", {"": "spoken"}),
    ],
)
def test_evaluation_plan_schema_and_runtime_reject_the_same_prompt_values(
    field: str, value: object
) -> None:
    schema = json.loads(
        (ROOT / "configs" / "schemas" / "evaluation-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
    plan = _evaluation_plan()
    plan["prompts"][0][field] = value

    with pytest.raises(ValueError):
        build_evaluation_matrix(plan, MODEL_REVISION)
    assert list(Draft202012Validator(schema).iter_errors(plan))


def test_candidate_expansion_keeps_primary_seed_first_and_deduplicates() -> None:
    rows = expand_candidates([_request()], [1701, 4242, 1087, 1701])

    assert [row["seed"] for row in rows] == [4242, 1701, 1087]
    assert [row["candidate_index"] for row in rows] == [1, 2, 3]
    assert [row["request_id"].rsplit("__s", 1)[1] for row in rows] == [
        "4242",
        "1701",
        "1087",
    ]
    assert all(row["candidate_of"] == _request()["request_id"] for row in rows)
    assert all(row["selection_required"] is True for row in rows)


@pytest.mark.parametrize(
    "reference_file",
    ["../reference.wav", "refs/../../reference.wav", "/tmp/reference.wav", r"refs\reference.wav"],
)
def test_reference_resolution_rejects_paths_outside_private_refs(
    tmp_path: Path, reference_file: str
) -> None:
    request = _request()
    request["reference_file"] = reference_file

    with pytest.raises(ValueError, match="private/upload/refs"):
        resolve_reference_path(tmp_path, request, require_exists=False)


def test_reference_resolution_accepts_only_existing_files_when_requested(
    tmp_path: Path,
) -> None:
    expected = tmp_path / "upload" / "refs" / "neutral-reference.wav"
    expected.parent.mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        resolve_reference_path(tmp_path, _request())

    expected.write_bytes(b"private fixture")
    assert resolve_reference_path(tmp_path, _request()) == expected.resolve()


def test_output_selection_never_overwrites_an_existing_render(tmp_path: Path) -> None:
    first = next_output_path(tmp_path, _request()["request_id"])
    first.parent.mkdir(parents=True)
    first.write_bytes(b"existing render")

    second = next_output_path(tmp_path, _request()["request_id"])
    second.write_bytes(b"retry")
    third = next_output_path(tmp_path, _request()["request_id"])

    assert first.name.endswith("__s4242.wav")
    assert second.name.endswith("__s4242__r2.wav")
    assert third.name.endswith("__s4242__r3.wav")
    assert first.parent == tmp_path / "results" / "raw" / "cosyvoice3"


def test_output_selection_rejects_request_id_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="request_id"):
        next_output_path(tmp_path, "../../escape")


def test_request_packs_are_immutable(tmp_path: Path) -> None:
    path = tmp_path / "private" / "upload" / "requests.jsonl"
    original = [_request()]

    write_jsonl_immutable(path, original)
    write_jsonl_immutable(path, original)

    with pytest.raises(FileExistsError, match="refusing to replace"):
        write_jsonl_immutable(path, [_request(seed=1701)])


def test_request_pack_creation_cannot_replace_a_racing_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "upload" / "requests.jsonl"
    path.parent.mkdir(parents=True)
    original = b"another writer won\n"
    path.write_bytes(original)
    real_exists = Path.exists

    def hide_target(candidate: Path) -> bool:
        if candidate == path:
            return False
        return real_exists(candidate)

    monkeypatch.setattr(Path, "exists", hide_target)

    with pytest.raises(FileExistsError, match="refusing to replace"):
        write_jsonl_immutable(path, [_request()])

    assert path.read_bytes() == original


def _write_runner_pack(private_root: Path, request: dict) -> Path:
    reference = private_root / "upload" / "refs" / "neutral-reference.wav"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"private fixture")
    request["reference_sha256"] = hashlib.sha256(reference.read_bytes()).hexdigest()
    request["request_id"] = request_identity(request)
    request_file = private_root / "upload" / "requests.jsonl"
    write_jsonl_immutable(request_file, [request])
    (private_root / "upload" / "private-profile.json").write_text(
        json.dumps({"schema_version": 1, "fixture": "speaker-agnostic"}),
        encoding="utf-8",
    )
    return reference


def test_runner_keeps_repository_pins_separate_from_external_private_paths(
    tmp_path: Path,
) -> None:
    private_root = tmp_path / "authorised-private-root"
    reference = _write_runner_pack(private_root, _request())
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_cosyvoice3.py"),
        "--root",
        str(ROOT),
        "--private-root",
        str(private_root),
        "--validate-only",
        "--smoke",
    ]

    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "validated 1 private CosyVoice requests"

    reference.write_bytes(b"changed fixture")
    rejected = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert "private reference hash changed" in rejected.stderr


def test_runner_rejects_request_bound_to_a_different_repository_model_pin(
    tmp_path: Path,
) -> None:
    private_root = tmp_path / "authorised-private-root"
    request = _request()
    request["model_revision"] = "0" * 40
    _write_runner_pack(private_root, request)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_cosyvoice3.py"),
        "--root",
        str(ROOT),
        "--private-root",
        str(private_root),
        "--validate-only",
        "--smoke",
    ]

    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)

    assert completed.returncode != 0
    assert "reviewed model revision" in completed.stderr


def test_runner_requires_an_external_private_root() -> None:
    environment = os.environ.copy()
    environment.pop("VOICE_KIT_PRIVATE_ROOT", None)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_cosyvoice3.py"),
        "--root",
        str(ROOT),
        "--validate-only",
        "--smoke",
    ]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "--private-root or VOICE_KIT_PRIVATE_ROOT" in completed.stderr


def test_runner_accepts_private_root_from_environment(tmp_path: Path) -> None:
    private_root = tmp_path / "authorised-private-root"
    _write_runner_pack(private_root, _request())
    environment = os.environ.copy()
    environment["VOICE_KIT_PRIVATE_ROOT"] = str(private_root)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_cosyvoice3.py"),
        "--root",
        str(ROOT),
        "--validate-only",
        "--smoke",
    ]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "validated 1 private CosyVoice requests"


def test_runner_rejects_request_pack_outside_private_root(tmp_path: Path) -> None:
    private_root = tmp_path / "authorised-private-root"
    _write_runner_pack(private_root, _request())
    outside = tmp_path / "outside" / "requests.jsonl"
    outside.parent.mkdir()
    outside.write_text("private fixture must not be read", encoding="utf-8")
    environment = os.environ.copy()
    environment.pop("VOICE_KIT_PRIVATE_ROOT", None)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_cosyvoice3.py"),
        "--root",
        str(ROOT),
        "--private-root",
        str(private_root),
        "--requests",
        str(outside),
        "--validate-only",
        "--smoke",
    ]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "private paths must resolve beneath the private root" in completed.stderr
