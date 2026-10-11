import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from voice_replication_kit.cli import _discover_repository_root, _dispatch as main
from voice_replication_kit.private_root import (
    initialise_private_root,
    resolve_private_root,
)


MARKER = ".voice-replication-private.json"
EXPECTED_MARKER = {
    "schema_version": 1,
    "purpose": "private voice workspace",
}
EXPECTED_DIRECTORIES = {
    "upload/refs",
    "runtime/cosyvoice",
    "runtime/models",
    "runtime/venv",
    "evaluation",
    "results/raw",
}


@pytest.fixture
def repository_root(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    return repository


def test_private_root_is_required(repository_root: Path) -> None:
    with pytest.raises(ValueError, match="--private-root or VOICE_KIT_PRIVATE_ROOT"):
        resolve_private_root(repository_root, None, {})


def test_explicit_private_root_takes_precedence_over_environment(
    tmp_path: Path, repository_root: Path
) -> None:
    explicit = tmp_path / "explicit"
    environment = tmp_path / "environment"

    resolved = resolve_private_root(
        repository_root,
        explicit,
        {"VOICE_KIT_PRIVATE_ROOT": str(environment)},
    )

    assert resolved == explicit.resolve()


def test_private_root_can_come_from_environment(
    tmp_path: Path, repository_root: Path
) -> None:
    private = tmp_path / "from-environment"

    resolved = resolve_private_root(
        repository_root,
        None,
        {"VOICE_KIT_PRIVATE_ROOT": str(private)},
    )

    assert resolved == private.resolve()


@pytest.mark.parametrize("relative_path", (Path(), Path("private")))
def test_private_root_rejects_checkout_and_descendants(
    repository_root: Path, relative_path: Path
) -> None:
    candidate = repository_root / relative_path

    with pytest.raises(ValueError, match="outside the Git checkout"):
        resolve_private_root(repository_root, candidate, {})


def test_private_root_rejects_resolved_directory_alias(
    tmp_path: Path, repository_root: Path
) -> None:
    inside = repository_root / "private"
    inside.mkdir()
    alias = tmp_path / "repository-alias"

    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(repository_root)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(f"Windows denied junction creation: {result.stderr.strip()}")
    else:
        try:
            alias.symlink_to(repository_root, target_is_directory=True)
        except OSError as error:
            pytest.skip(f"operating system denied directory symlink creation: {error}")

    with pytest.raises(ValueError, match="outside the Git checkout"):
        resolve_private_root(repository_root, alias / "private", {})


def test_initialise_private_root_creates_only_fixed_layout_and_marker(
    tmp_path: Path, repository_root: Path
) -> None:
    private = tmp_path / "authorised-private-root"

    created = initialise_private_root(repository_root, private)

    assert {path.relative_to(private).as_posix() for path in created} == (
        EXPECTED_DIRECTORIES
    )
    assert json.loads((private / MARKER).read_text(encoding="utf-8")) == (
        EXPECTED_MARKER
    )
    assert {
        path.relative_to(private).as_posix() + ("/" if path.is_dir() else "")
        for path in private.rglob("*")
    } == {
        "upload/",
        "upload/refs/",
        "runtime/",
        "runtime/cosyvoice/",
        "runtime/models/",
        "runtime/venv/",
        "evaluation/",
        "results/",
        "results/raw/",
        MARKER,
    }


def test_initialise_private_root_refuses_non_empty_unmarked_directory(
    tmp_path: Path, repository_root: Path
) -> None:
    private = tmp_path / "existing"
    private.mkdir()
    existing = private / "keep.txt"
    existing.write_text("do not change", encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty.*marker"):
        initialise_private_root(repository_root, private)

    assert existing.read_text(encoding="utf-8") == "do not change"
    assert list(private.iterdir()) == [existing]


def test_initialise_private_root_repairs_valid_marked_layout(
    tmp_path: Path, repository_root: Path
) -> None:
    private = tmp_path / "authorised-private-root"
    initialise_private_root(repository_root, private)
    missing = private / "runtime" / "models"
    missing.rmdir()

    created = initialise_private_root(repository_root, private)

    assert missing.is_dir()
    assert {path.relative_to(private).as_posix() for path in created} == (
        EXPECTED_DIRECTORIES
    )
    assert json.loads((private / MARKER).read_text(encoding="utf-8")) == (
        EXPECTED_MARKER
    )


def test_initialise_private_root_refuses_invalid_marker_without_changes(
    tmp_path: Path, repository_root: Path
) -> None:
    private = tmp_path / "existing"
    private.mkdir()
    marker = private / MARKER
    marker.write_text('{"schema_version": 2}', encoding="utf-8")

    with pytest.raises(ValueError, match="valid private workspace marker"):
        initialise_private_root(repository_root, private)

    assert marker.read_text(encoding="utf-8") == '{"schema_version": 2}'
    assert list(private.iterdir()) == [marker]


def test_initialise_private_root_rejects_checkout_before_creating_files(
    repository_root: Path,
) -> None:
    inside = repository_root / "private"

    with pytest.raises(ValueError, match="outside the Git checkout"):
        initialise_private_root(repository_root, inside)

    assert not inside.exists()


def test_init_private_command_initialises_external_workspace(
    tmp_path: Path, repository_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = tmp_path / "authorised-private-root"
    monkeypatch.chdir(repository_root)

    exit_code = main(["init-private", "--private-root", str(private)])

    assert exit_code == 0
    assert json.loads((private / MARKER).read_text(encoding="utf-8")) == (
        EXPECTED_MARKER
    )


def test_init_private_command_rejects_checkout_from_nested_working_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    private = repository / ".task-2-cli-private-regression"
    assert not private.exists()
    monkeypatch.chdir(repository / "tests")

    try:
        with pytest.raises(ValueError, match="outside the Git checkout"):
            main(["init-private", "--private-root", f"../{private.name}"])
    finally:
        if private.exists():
            shutil.rmtree(private)

    assert not private.exists()


def test_repository_discovery_fails_closed_without_git_checkout(
    tmp_path: Path,
) -> None:
    installed_cli = tmp_path / "site-packages" / "voice_replication_kit" / "cli.py"
    installed_cli.parent.mkdir(parents=True)
    installed_cli.touch()

    with pytest.raises(RuntimeError, match="trusted voice-kit source root"):
        _discover_repository_root(installed_cli)
