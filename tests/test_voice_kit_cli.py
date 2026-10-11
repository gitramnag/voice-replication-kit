import hashlib
from importlib.metadata import metadata
import json
import os
from pathlib import Path
import subprocess
import sysconfig
from typing import Mapping

import pytest

from voice_replication_kit.requests import request_identity


COMMANDS = (
    "init-private",
    "validate-profile",
    "build-requests",
    "build-matrix",
    "build-blind-map",
    "render",
    "audit",
)
ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "29e01c4e8d000f4bcd70751be16fa94bf3d85a18"


def installed_voice_kit() -> Path:
    scripts = Path(sysconfig.get_path("scripts"))
    candidates = (scripts / "voice-kit.exe", scripts / "voice-kit")
    command = next((candidate for candidate in candidates if candidate.is_file()), None)
    assert command is not None, "voice-kit console script is not installed"
    return command


def run_voice_kit(
    *arguments: str, environment: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(installed_voice_kit()), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _write_render_inputs(tmp_path: Path) -> tuple[Path, str, str]:
    private = tmp_path / "private-runtime-path-must-not-leak"
    initialised = run_voice_kit("init-private", "--private-root", str(private))
    assert initialised.returncode == 0, initialised.stderr

    reference = private / "upload" / "refs" / "synthetic-reference.wav"
    reference.write_bytes(b"synthetic private reference bytes")
    reference_text = "Synthetic private transcript must not leak."
    request_text = "Synthetic request text must not leak."
    request = {
        "schema_version": 1,
        "prompt_id": "synthetic_prompt",
        "source_segment_id": "synthetic-segment",
        "unit_index": 1,
        "style": "narration_neutral",
        "language": "en",
        "text": request_text,
        "seed": 4242,
        "reference_file": "refs/synthetic-reference.wav",
        "reference_text": reference_text,
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "reference_text_sha256": hashlib.sha256(
            reference_text.encode("utf-8")
        ).hexdigest(),
        "text_shape": "connected_sentence",
        "model_revision": MODEL_REVISION,
        "pronunciation_overrides": {},
    }
    request["request_id"] = request_identity(request)
    (private / "upload" / "requests.jsonl").write_text(
        json.dumps(request) + "\n", encoding="utf-8"
    )
    (private / "upload" / "private-profile.json").write_text(
        json.dumps({"schema_version": 1, "fixture": "speaker-agnostic"}),
        encoding="utf-8",
    )
    return private, reference_text, request_text


def test_package_supports_python_310() -> None:
    assert metadata("voice-replication-kit")["Requires-Python"] == ">=3.10"


def test_top_level_help_lists_every_public_command() -> None:
    result = run_voice_kit("--help")

    assert result.returncode == 0
    assert "Build and reuse an authorised private voice" in result.stdout
    for command in COMMANDS:
        assert command in result.stdout


@pytest.mark.parametrize("command", COMMANDS)
def test_command_help_is_reachable(command: str) -> None:
    result = run_voice_kit(command, "--help")

    assert result.returncode == 0
    assert f"voice-kit {command}" in result.stdout


def test_malformed_private_input_has_stable_private_safe_failure(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private-name-must-not-leak"
    upload = private / "upload"
    upload.mkdir(parents=True)
    private_payload = "speaker-private-content-must-not-leak"
    (upload / "private-profile.json").write_text(private_payload, encoding="utf-8")

    result = run_voice_kit("validate-profile", "--private-root", str(private))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: private profile: file is missing or malformed"
    )
    assert str(private) not in result.stderr
    assert private_payload not in result.stderr
    assert "Traceback" not in result.stderr


def test_changed_reference_hash_has_a_specific_private_safe_failure(
    tmp_path: Path,
) -> None:
    import json

    private = tmp_path / "private-path-must-not-leak"
    reference = private / "upload" / "refs" / "synthetic-reference.wav"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"synthetic private reference bytes")
    private_transcript = "synthetic private transcript must not leak"
    profile = {
        "schema_version": 1,
        "model": "cosyvoice3",
        "recipes": {
            "narration_neutral": {
                "reference_file": "refs/synthetic-reference.wav",
                "reference_text": private_transcript,
                "reference_sha256": "0" * 64,
                "seed": 1087,
                "text_shape": "connected_sentence",
            }
        },
    }
    (private / "upload" / "private-profile.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )

    result = run_voice_kit("validate-profile", "--private-root", str(private))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: private profile: reference hash changed"
    )
    assert str(private) not in result.stderr
    assert private_transcript not in result.stderr


def test_unexpected_failure_is_not_misclassified(monkeypatch: pytest.MonkeyPatch) -> None:
    from voice_replication_kit import cli

    def fail_unexpectedly(_args: object) -> int:
        raise ValueError("synthetic programmer failure")

    parser = cli.build_parser()
    args = parser.parse_args(["init-private", "--private-root", "unused"])
    args.handler = fail_unexpectedly
    monkeypatch.setattr(cli, "build_parser", lambda: _FixedParser(args))

    with pytest.raises(ValueError, match="programmer failure"):
        cli.main(["init-private"])


@pytest.mark.parametrize("matrix_bytes", [None, b"\xff\xfeprivate matrix"])
def test_private_matrix_read_failures_are_safe(
    tmp_path: Path, matrix_bytes: bytes | None
) -> None:
    private = tmp_path / "private-matrix-path-must-not-leak"
    evaluation = private / "evaluation"
    evaluation.mkdir(parents=True)
    matrix = evaluation / "matrix.jsonl"
    if matrix_bytes is not None:
        matrix.write_bytes(matrix_bytes)

    result = run_voice_kit("build-blind-map", "--private-root", str(private))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: evaluation matrix: file is missing or malformed"
    )
    assert str(private) not in result.stderr
    assert "private matrix" not in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_private_root_has_exact_private_safe_reason() -> None:
    environment = os.environ.copy()
    environment.pop("VOICE_KIT_PRIVATE_ROOT", None)

    result = run_voice_kit("render", "--validate-only", environment=environment)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: private root: external path is required"
    )
    assert "Traceback" not in result.stderr


def test_inside_project_private_root_has_exact_direction() -> None:
    private = ROOT / "private-sentinel-for-cli-test"
    assert not private.exists()

    result = run_voice_kit("init-private", "--private-root", str(private))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: private root: path is inside the public project"
    )
    assert str(private) not in result.stderr
    assert "private-sentinel-for-cli-test" not in result.stderr
    assert not private.exists()


def test_wrong_accept_smoke_id_has_exact_private_safe_reason(tmp_path: Path) -> None:
    private, reference_text, request_text = _write_render_inputs(tmp_path)
    wrong_id = "private-wrong-id-must-not-leak"

    result = run_voice_kit(
        "render",
        "--private-root",
        str(private),
        "--accept-smoke",
        wrong_id,
        "--validate-only",
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: render inputs: smoke ID does not match a successful smoke "
        "render for this request pack"
    )
    for private_value in (str(private), wrong_id, reference_text, request_text):
        assert private_value not in result.stderr


def test_missing_accept_smoke_id_has_exact_private_safe_reason(
    tmp_path: Path,
) -> None:
    private, reference_text, request_text = _write_render_inputs(tmp_path)

    result = run_voice_kit(
        "render", "--private-root", str(private), "--validate-only"
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: render inputs: smoke ID is required for a full batch"
    )
    for private_value in (str(private), reference_text, request_text):
        assert private_value not in result.stderr


def test_render_without_runtime_has_exact_private_safe_reason(tmp_path: Path) -> None:
    private, reference_text, request_text = _write_render_inputs(tmp_path)

    result = run_voice_kit(
        "render", "--private-root", str(private), "--smoke"
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: render inputs: pinned runtime cannot be verified"
    )
    for private_value in (
        str(private),
        "runtime/cosyvoice",
        reference_text,
        request_text,
    ):
        assert private_value not in result.stderr


def test_evaluation_schema_mismatch_has_exact_private_safe_reason(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private-plan-path-must-not-leak"
    initialised = run_voice_kit("init-private", "--private-root", str(private))
    assert initialised.returncode == 0, initialised.stderr
    reference = private / "upload" / "refs" / "synthetic-reference.wav"
    reference.write_bytes(b"synthetic private reference bytes")
    reference_text = "Synthetic evaluation transcript must not leak."
    experiment_question = "Private experiment question must not leak."
    plan = {
        "schema_version": 2,
        "experiment_question": experiment_question,
        "prompts": [
            {
                "prompt_id": "synthetic_prompt",
                "source_segment_id": "synthetic-segment",
                "unit_index": 1,
                "style": "narration_neutral",
                "language": "en",
                "text": "Synthetic evaluation sentence.",
                "pronunciation_overrides": {},
            }
        ],
        "references": [
            {
                "reference_key": "synthetic-ref",
                "reference_file": "refs/synthetic-reference.wav",
                "reference_text": reference_text,
                "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
            }
        ],
        "seeds": [4242],
        "text_shapes": ["connected_sentence"],
    }
    (private / "upload" / "evaluation-plan.json").write_text(
        json.dumps(plan), encoding="utf-8"
    )

    result = run_voice_kit("build-matrix", "--private-root", str(private))

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "voice-kit: evaluation plan: schema version must be 1"
    )
    for private_value in (
        str(private),
        experiment_question,
        reference_text,
        reference.name,
    ):
        assert private_value not in result.stderr


def test_troubleshooting_uses_exact_public_cli_messages() -> None:
    troubleshooting = (ROOT / "docs" / "troubleshooting.md").read_text(
        encoding="utf-8"
    )
    expected_headings = (
        "voice-kit: private root: external path is required",
        "voice-kit: private root: path is inside the public project",
        "voice-kit: evaluation plan: schema version must be 1",
        "voice-kit: render inputs: pinned runtime cannot be verified",
        "voice-kit: render inputs: smoke ID is required for a full batch",
        "voice-kit: render inputs: smoke ID does not match a successful smoke "
        "render for this request pack",
    )
    for message in expected_headings:
        assert f"### `{message}`" in troubleshooting

    stale_headings = (
        "supply --private-root or VOICE_KIT_PRIVATE_ROOT",
        "private root must be outside the Git checkout",
        "refusing to replace existing request pack",
        "unknown production style",
    )
    for message in stale_headings:
        assert f"### `{message}`" not in troubleshooting


class _FixedParser:
    def __init__(self, args: object) -> None:
        self.args = args

    def parse_args(self, _argv: object) -> object:
        return self.args
