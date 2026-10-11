from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from voice_replication_kit.cli import _dispatch as main
from voice_replication_kit.private_root import initialise_private_root


ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"
REFERENCE_BYTES = b"real private WAV fixture bytes"
REFERENCE_TEXT = "A private transcript that must never be printed."


def _document() -> dict:
    return {
        "schema_version": 1,
        "title": "Private production document",
        "language": "en",
        "segments": [
            {
                "id": "opening",
                "intent": "neutral explanation",
                "text": "This is the prepared production sentence.",
                "pronunciation_overrides": {},
            }
        ],
    }


def _profile(reference_sha256: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "model": "cosyvoice3",
        "recipes": {
            "narration_neutral": {
                "reference_file": "refs/neutral-reference.wav",
                "reference_text": REFERENCE_TEXT,
                "reference_sha256": reference_sha256
                or hashlib.sha256(REFERENCE_BYTES).hexdigest(),
                "seed": 4242,
                "text_shape": "connected_sentence",
            }
        },
    }


@pytest.fixture
def private_root(tmp_path: Path) -> Path:
    private = tmp_path / "authorised-private-root"
    initialise_private_root(ROOT, private)
    upload = private / "upload"
    (upload / "refs" / "neutral-reference.wav").write_bytes(REFERENCE_BYTES)
    (upload / "private-profile.json").write_text(
        json.dumps(_profile()), encoding="utf-8"
    )
    (upload / "production-script.json").write_text(
        json.dumps(_document()), encoding="utf-8"
    )
    return private


def test_validate_profile_checks_real_reference_without_printing_private_values(
    private_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["validate-profile", "--private-root", str(private_root)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "validated 1 private profile recipe"
    assert REFERENCE_TEXT not in captured.out + captured.err
    assert hashlib.sha256(REFERENCE_BYTES).hexdigest() not in captured.out + captured.err


def test_validate_profile_rejects_a_missing_reference(private_root: Path) -> None:
    (private_root / "upload" / "refs" / "neutral-reference.wav").unlink()

    with pytest.raises(FileNotFoundError, match="private reference does not exist"):
        main(["validate-profile", "--private-root", str(private_root)])


def test_validate_profile_rejects_a_mismatched_reference_hash(
    private_root: Path,
) -> None:
    profile_path = private_root / "upload" / "private-profile.json"
    profile_path.write_text(json.dumps(_profile("f" * 64)), encoding="utf-8")

    with pytest.raises(ValueError, match="private reference hash changed"):
        main(["validate-profile", "--private-root", str(private_root)])


def test_build_requests_uses_reviewed_model_pin_and_default_private_paths(
    private_root: Path,
) -> None:
    exit_code = main(["build-requests", "--private-root", str(private_root)])

    output = private_root / "upload" / "requests.jsonl"
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert exit_code == 0
    assert len(rows) == 1
    assert rows[0]["model_revision"] == MODEL_REVISION
    assert rows[0]["reference_text"] == REFERENCE_TEXT


@pytest.mark.parametrize("option", ["--document", "--profile", "--output"])
def test_build_requests_rejects_every_supplied_path_outside_private_root(
    private_root: Path, tmp_path: Path, option: str
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="beneath the private root"):
        main(
            [
                "build-requests",
                "--private-root",
                str(private_root),
                option,
                str(outside),
            ]
        )


def test_build_requests_refuses_to_replace_a_different_existing_pack(
    private_root: Path,
) -> None:
    arguments = ["build-requests", "--private-root", str(private_root)]
    assert main(arguments) == 0
    output = private_root / "upload" / "requests.jsonl"
    original = output.read_bytes()
    document_path = private_root / "upload" / "production-script.json"
    document = _document()
    document["segments"][0]["text"] = "Changed prepared production text."
    document_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to replace"):
        main(arguments)

    assert output.read_bytes() == original


def test_build_requests_rejects_unknown_document_keys(private_root: Path) -> None:
    document_path = private_root / "upload" / "production-script.json"
    document_path.write_text(
        json.dumps(dict(_document(), private_note="unknown")), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="unexpected"):
        main(["build-requests", "--private-root", str(private_root)])
