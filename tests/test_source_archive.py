from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from voice_replication_kit import cli
from voice_replication_kit import audit_sources
from voice_replication_kit.audit_sources import AuditSourceError
from voice_replication_kit.privacy import run_audit


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = b"synthetic archive reference"
TRANSCRIPT = "Synthetic speaker-agnostic archive transcript."


def _is_repository_git_worktree() -> bool:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return False
    return (
        completed.returncode == 0
        and Path(completed.stdout.strip()).resolve() == ROOT.resolve()
    )


def _public_worktree_paths() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    paths: list[Path] = []
    for raw in listed:
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        if (ROOT / relative).is_file():
            paths.append(relative)
    return sorted(paths)


def _copy_public_worktree(destination_root: Path) -> None:
    for relative in _public_worktree_paths():
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)


def _archive_copy(tmp_path: Path) -> Path:
    archive = tmp_path / "voice-replication-kit-source-archive"
    _copy_public_worktree(archive)
    assert not (archive / ".git").exists()
    return archive


def _write_inputs(private: Path) -> None:
    upload = private / "upload"
    reference = upload / "refs" / "synthetic.wav"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_bytes(REFERENCE)
    digest = hashlib.sha256(REFERENCE).hexdigest()
    profile = {
        "schema_version": 1,
        "model": "cosyvoice3",
        "recipes": {
            "narration_neutral": {
                "reference_file": "refs/synthetic.wav",
                "reference_text": TRANSCRIPT,
                "reference_sha256": digest,
                "seed": 4242,
                "text_shape": "connected_sentence",
            }
        },
    }
    document = {
        "schema_version": 1,
        "title": "Synthetic archive document",
        "language": "en",
        "segments": [
            {
                "id": "archive-segment",
                "intent": "neutral explanation",
                "text": "This sentence verifies source archive execution.",
                "pronunciation_overrides": {},
            }
        ],
    }
    plan = {
        "schema_version": 1,
        "experiment_question": "Which synthetic archive candidate is clearest?",
        "prompts": [
            {
                "prompt_id": "archive_prompt_01",
                "source_segment_id": "archive-segment",
                "unit_index": 1,
                "style": "narration_neutral",
                "language": "en",
                "text": "This sentence checks the archive matrix.",
                "pronunciation_overrides": {},
            }
        ],
        "references": [
            {
                "reference_key": "archive-ref",
                "reference_file": "refs/synthetic.wav",
                "reference_text": TRANSCRIPT,
                "reference_sha256": digest,
            }
        ],
        "seeds": [4242],
        "text_shapes": ["connected_sentence"],
    }
    (upload / "private-profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (upload / "production-script.json").write_text(json.dumps(document), encoding="utf-8")
    (upload / "evaluation-plan.json").write_text(json.dumps(plan), encoding="utf-8")


@pytest.mark.skipif(
    os.environ.get("VOICE_KIT_SOURCE_ARCHIVE_SUITE") == "1",
    reason="the outer git-archive suite does not recurse",
)
@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_git_archive_zip_runs_the_full_test_suite(tmp_path: Path) -> None:
    archive_path = tmp_path / "voice-replication-kit.zip"
    extracted = tmp_path / "source-archive"
    subprocess.run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--output={archive_path}",
            "HEAD",
        ],
        cwd=ROOT,
        check=True,
    )
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extracted)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["VOICE_KIT_SOURCE_ARCHIVE_SUITE"] = "1"
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (str(extracted / "src"), existing_pythonpath)
        if part
    )

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=extracted,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_source_archive_supports_the_private_command_journey_from_nested_cwd(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    archive = _archive_copy(tmp_path)
    package_file = archive / "src" / "voice_replication_kit" / "cli.py"
    nested = archive / "docs" / "passes"
    private = tmp_path / "external-private-root"

    assert cli._discover_repository_root(package_file) == archive.resolve()
    monkeypatch.setattr(
        cli,
        "_discover_repository_roots",
        lambda package_file=package_file: (archive.resolve(), archive.resolve()),
    )
    monkeypatch.chdir(nested)

    assert cli.main(["init-private", "--private-root", str(private)]) == 0
    _write_inputs(private)
    assert cli.main(["validate-profile", "--private-root", str(private)]) == 0
    assert cli.main(["build-requests", "--private-root", str(private)]) == 0
    assert cli.main(["build-matrix", "--private-root", str(private)]) == 0
    assert cli.main(["build-blind-map", "--private-root", str(private)]) == 0
    assert cli.main(
        ["render", "--private-root", str(private), "--smoke", "--validate-only"]
    ) == 0

    inside = archive / "private"
    assert cli.main(["init-private", "--private-root", str(inside)]) == 1
    assert not inside.exists()
    assert (
        "voice-kit: private root: path is inside the public project"
        in capsys.readouterr().err
    )


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_source_archive_history_audit_fails_with_a_clear_git_requirement(
    tmp_path: Path, capsys
) -> None:
    archive = _archive_copy(tmp_path)

    assert run_audit(archive, "history") == 2
    assert capsys.readouterr().out.strip() == "history scan requires a Git worktree"


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_source_archive_discovery_falls_back_when_git_is_not_installed(
    tmp_path: Path, monkeypatch
) -> None:
    archive = _archive_copy(tmp_path)
    package_file = archive / "src" / "voice_replication_kit" / "cli.py"

    def missing_git(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("git executable absent")

    monkeypatch.setattr(cli.subprocess, "run", missing_git)

    assert cli._discover_repository_root(package_file) == archive.resolve()


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_archive_inside_enclosing_git_uses_outer_publication_boundary(
    tmp_path: Path, monkeypatch
) -> None:
    enclosing = tmp_path / "unrelated-publication-worktree"
    enclosing.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=enclosing, check=True)
    archive = enclosing / "vendor" / "voice-replication-kit"
    _copy_public_worktree(archive)
    package_file = archive / "src" / "voice_replication_kit" / "cli.py"
    resource_root, publication_root = cli._discover_repository_roots(package_file)
    assert resource_root == archive.resolve()
    assert publication_root == enclosing.resolve()
    monkeypatch.setattr(
        cli,
        "_discover_repository_roots",
        lambda package_file=package_file: (resource_root, publication_root),
    )

    inside_publication = enclosing / "private-sibling"
    assert cli.main(["init-private", "--private-root", str(inside_publication)]) == 1
    assert not inside_publication.exists()

    external = tmp_path / "external-private-root"
    assert cli.main(["init-private", "--private-root", str(external)]) == 0
    assert (external / ".voice-replication-private.json").is_file()


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_history_audit_without_git_fails_safely(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    archive = _archive_copy(tmp_path)

    def missing_git(*_args: object, **_kwargs: object) -> object:
        raise AuditSourceError("Git is unavailable for publication audit")

    monkeypatch.setattr(audit_sources, "_probe_git", missing_git)

    assert run_audit(archive, "history") == 2
    output = capsys.readouterr().out
    assert output.strip() == "audit source error: Git is unavailable for publication audit"
    assert "Traceback" not in output
