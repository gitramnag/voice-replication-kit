from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from voice_replication_kit.cli import _dispatch as main
from voice_replication_kit.private_root import initialise_private_root


ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"
REFERENCE_BYTES = b"synthetic private reference WAV bytes"
REFERENCE_TEXT = "A synthetic private transcript that must not be printed."
REFERENCE_KEY = "synthetic-ref"


def _plan(reference_sha256: str | None = None) -> dict:
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
                "text": "This is a synthetic evaluation sentence.",
                "pronunciation_overrides": {},
            }
        ],
        "references": [
            {
                "reference_key": REFERENCE_KEY,
                "reference_file": "refs/synthetic-reference.wav",
                "reference_text": REFERENCE_TEXT,
                "reference_sha256": reference_sha256
                or hashlib.sha256(REFERENCE_BYTES).hexdigest(),
            }
        ],
        "seeds": [1087, 4242],
        "text_shapes": ["short_clause", "connected_sentence"],
    }


@pytest.fixture
def private_root(tmp_path: Path) -> Path:
    private = tmp_path / "authorised-private-root"
    initialise_private_root(ROOT, private)
    upload = private / "upload"
    (upload / "refs" / "synthetic-reference.wav").write_bytes(REFERENCE_BYTES)
    (upload / "evaluation-plan.json").write_text(
        json.dumps(_plan()), encoding="utf-8"
    )
    return private


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def test_build_matrix_uses_default_private_paths_and_reviewed_model_pin(
    private_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["build-matrix", "--private-root", str(private_root)])

    output = private_root / "evaluation" / "matrix.jsonl"
    rows = _read_jsonl(output)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert len(rows) == 4
    assert {row["model_revision"] for row in rows} == {MODEL_REVISION}
    assert REFERENCE_TEXT not in captured.out + captured.err
    assert REFERENCE_KEY not in captured.out + captured.err
    assert hashlib.sha256(REFERENCE_BYTES).hexdigest() not in captured.out + captured.err


def test_build_matrix_checks_the_real_reference_hash_before_writing(
    private_root: Path,
) -> None:
    plan_path = private_root / "upload" / "evaluation-plan.json"
    plan_path.write_text(json.dumps(_plan("f" * 64)), encoding="utf-8")

    with pytest.raises(ValueError, match="private reference hash changed"):
        main(["build-matrix", "--private-root", str(private_root)])

    assert not (private_root / "evaluation" / "matrix.jsonl").exists()


@pytest.mark.parametrize("option", ["--plan", "--output"])
def test_build_matrix_rejects_supplied_paths_outside_private_root(
    private_root: Path, tmp_path: Path, option: str
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="beneath the private root"):
        main(
            [
                "build-matrix",
                "--private-root",
                str(private_root),
                option,
                str(outside),
            ]
        )


def test_build_blind_map_writes_allowlisted_rows_and_a_separate_secret_map(
    private_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["build-matrix", "--private-root", str(private_root)]) == 0
    capsys.readouterr()

    exit_code = main(["build-blind-map", "--private-root", str(private_root)])

    visible_path = private_root / "evaluation" / "blind-candidates.jsonl"
    secret_path = private_root / "evaluation" / "unblinding-map.json"
    matrix_rows = _read_jsonl(private_root / "evaluation" / "matrix.jsonl")
    visible = _read_jsonl(visible_path)
    secret = json.loads(secret_path.read_text("utf-8"))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert set(secret) == {row["blind_label"] for row in visible}
    assert set(secret.values()) == {row["request_id"] for row in matrix_rows}
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
    public_text = visible_path.read_text("utf-8") + captured.out + captured.err
    for row in matrix_rows:
        for private_value in (
            row["request_id"],
            row["reference_key"],
            row["reference_file"],
            row["reference_text"],
            row["reference_sha256"],
            row["reference_text_sha256"],
            row["model_revision"],
            str(row["seed"]),
        ):
            assert private_value not in public_text


@pytest.mark.parametrize("option", ["--matrix", "--output", "--secret-output"])
def test_build_blind_map_rejects_supplied_paths_outside_private_root(
    private_root: Path, tmp_path: Path, option: str
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="beneath the private root"):
        main(
            [
                "build-blind-map",
                "--private-root",
                str(private_root),
                option,
                str(outside),
            ]
        )


def test_all_evaluation_outputs_refuse_different_existing_content(
    private_root: Path,
) -> None:
    matrix_args = ["build-matrix", "--private-root", str(private_root)]
    blind_args = ["build-blind-map", "--private-root", str(private_root)]
    assert main(matrix_args) == 0
    assert main(matrix_args) == 0
    assert main(blind_args) == 0
    assert main(blind_args) == 0

    matrix = private_root / "evaluation" / "matrix.jsonl"
    matrix.write_text("different matrix\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to replace"):
        main(matrix_args)

    matrix.unlink()
    assert main(matrix_args) == 0
    visible = private_root / "evaluation" / "blind-candidates.jsonl"
    visible.write_text("different visible rows\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to replace"):
        main(blind_args)

    visible.unlink()
    secret = private_root / "evaluation" / "unblinding-map.json"
    secret.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to replace"):
        main(blind_args)
