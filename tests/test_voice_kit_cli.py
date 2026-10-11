from importlib.metadata import metadata
from pathlib import Path
import subprocess
import sysconfig

import pytest


COMMANDS = (
    "init-private",
    "validate-profile",
    "build-requests",
    "build-matrix",
    "build-blind-map",
    "render",
    "audit",
)


def installed_voice_kit() -> Path:
    scripts = Path(sysconfig.get_path("scripts"))
    candidates = (scripts / "voice-kit.exe", scripts / "voice-kit")
    command = next((candidate for candidate in candidates if candidate.is_file()), None)
    assert command is not None, "voice-kit console script is not installed"
    return command


def run_voice_kit(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(installed_voice_kit()), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


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


class _FixedParser:
    def __init__(self, args: object) -> None:
        self.args = args

    def parse_args(self, _argv: object) -> object:
        return self.args
