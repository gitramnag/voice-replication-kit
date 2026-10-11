from __future__ import annotations

from pathlib import Path, PurePosixPath
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from voice_replication_kit.privacy import FORBIDDEN_EXTENSIONS, FORBIDDEN_NAMES


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_NAME = "gitramnag"
PUBLIC_EMAIL = "315322897+gitramnag@users.noreply.github.com"


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


def git_lines(root: Path, *arguments: str) -> list[str]:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.splitlines()


def positions_in_order(text: str, required: list[str]) -> bool:
    position = -1
    for item in required:
        position = text.find(item, position + 1)
        if position < 0:
            return False
    return True


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_tracked_text_uses_the_pseudonymous_owner_identity() -> None:
    private_terms_value = os.environ.get("VOICE_KIT_PRIVATE_TERMS_FILE")
    if not private_terms_value:
        pytest.skip("owner-controlled private terms file was not supplied")
    private_terms_file = Path(private_terms_value).expanduser().resolve(strict=True)
    completed = subprocess.run(
        ["git", "grep", "-n", "-I", "-F", "-f", str(private_terms_file), "--", "."],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode in {0, 1}, completed.stderr
    assert completed.stdout == ""
    assert PUBLIC_NAME == "gitramnag"
    assert PUBLIC_EMAIL == "315322897+gitramnag@users.noreply.github.com"


def test_clean_room_scripts_contain_every_release_gate() -> None:
    required = [
        "git clone --no-local",
        "python -m pip install --require-hashes -r configs/public-tools-lock.txt",
        "python -m pip install --no-build-isolation --no-deps -e .",
        "python -m pytest",
        "python -m voice_replication_kit.corpus",
        "python tools/build_scorecard.py --check",
        "python tools/build_diagrams.py --check",
        "python scripts/check_links.py",
        "voice-kit audit --mode tree",
        "voice-kit audit --mode history",
        "git status --porcelain",
    ]
    for relative in (
        "scripts/clean_room_audit.ps1",
        "scripts/clean_room_audit.sh",
    ):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert positions_in_order(script, required), relative


def test_clean_room_scripts_forward_an_optional_external_private_terms_file() -> None:
    for relative in (
        "scripts/clean_room_audit.ps1",
        "scripts/clean_room_audit.sh",
    ):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert "VOICE_KIT_PRIVATE_TERMS_FILE" in script, relative
        assert "--private-terms-file" in script, relative


def test_clean_room_scripts_isolate_the_editable_install_in_the_clone() -> None:
    for relative in (
        "scripts/clean_room_audit.ps1",
        "scripts/clean_room_audit.sh",
    ):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert positions_in_order(
            script,
            [
                "python -m venv .venv",
                "python -m pip install --require-hashes -r configs/public-tools-lock.txt",
                "python -m pip install --no-build-isolation --no-deps -e .",
            ],
        ), relative


def test_public_tool_lock_is_hash_pinned_and_used_by_ci() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lock = (ROOT / "configs" / "public-tools-lock.txt").read_text(
        encoding="utf-8"
    )
    requirements = [
        line for line in lock.splitlines() if line and not line.startswith((" ", "#"))
    ]
    assert requirements
    assert "jsonschema==4.25.1" in lock
    assert "pytest==9.0.3" in lock
    assert project.count('"setuptools==84.0.0"') == 2
    assert "setuptools==84.0.0" in lock
    assert "exceptiongroup==" in lock
    assert "tomli==" in lock
    assert "--universal --python-version 3.10 --generate-hashes" in lock
    assert "exceptiongroup==1.3.1 ; python_full_version < '3.11'" in lock
    assert "tomli==2.5.0 ; python_full_version < '3.11'" in lock
    assert "rpds-py==0.30.0 ; python_full_version < '3.11'" in lock
    assert "rpds-py==2026.9.1 ; python_full_version >= '3.11'" in lock
    assert "typing-extensions==4.16.0 ; python_full_version < '3.13'" in lock
    assert "colorama==0.4.6 ; sys_platform == 'win32'" in lock
    assert all("==" in requirement for requirement in requirements)
    assert lock.count("--hash=sha256:") >= len(requirements)

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert positions_in_order(
        workflow,
        [
            "python -m pip install --require-hashes -r configs/public-tools-lock.txt",
            "python -m pip install --no-build-isolation --no-deps -e .",
        ],
    )


def test_clean_room_scripts_run_the_complete_suite_by_default() -> None:
    for relative in (
        "scripts/clean_room_audit.ps1",
        "scripts/clean_room_audit.sh",
    ):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert "python -m pytest" in script, relative
        assert "python -m pytest -k" not in script, relative


def test_actions_use_immutable_full_length_revisions() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    uses = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", workflow, re.MULTILINE)
    assert uses
    for action in uses:
        _name, separator, revision = action.rpartition("@")
        assert separator and re.fullmatch(r"[0-9a-f]{40}", revision), action


def test_clean_room_job_checks_out_complete_history() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    clean_room = workflow.split("  clean-room:", 1)[1]
    checkout = clean_room.split("- name: Set up Python", 1)[0]
    assert re.search(r"with:\s*\n\s+fetch-depth:\s*0\b", checkout)


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_sanitized_history_needs_no_reviewed_exceptions() -> None:
    manifest = json.loads(
        (ROOT / "configs" / "reviewed-history-exceptions.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest == {"version": 1, "exceptions": []}

    completed = subprocess.run(
        ["voice-kit", "audit", "--mode", "history", "--root", str(ROOT)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "publication boundary check passed"


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_editable_install_clone_passes_the_publication_tree_audit(
    tmp_path: Path,
) -> None:
    clone = tmp_path / "editable-install-clone"
    subprocess.run(
        ["git", "clone", "--no-local", "--quiet", "--", str(ROOT), str(clone)],
        check=True,
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", ".venv"],
        cwd=clone,
        env=environment,
        check=True,
    )
    venv_python = clone / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    venv_voice_kit = clone / ".venv" / (
        "Scripts/voice-kit.exe" if os.name == "nt" else "bin/voice-kit"
    )
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--no-deps", "-e", "."],
        cwd=clone,
        env=environment,
        check=True,
    )
    subprocess.run(
        [str(venv_python), "-m", "pytest", "-q", "tests/test_audit_sources.py"],
        cwd=clone,
        env=environment,
        check=True,
    )

    help_result = subprocess.run(
        [str(venv_voice_kit), "--help"],
        cwd=clone,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    tree_result = subprocess.run(
        [str(venv_voice_kit), "audit", "--root", ".", "--mode", "tree"],
        cwd=clone,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    check_result = subprocess.run(
        [str(venv_python), "scripts/check_publication.py", "--root", "."],
        cwd=clone,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    for completed in (help_result, tree_result, check_result):
        assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "publication boundary check passed" in tree_result.stdout
    assert "publication boundary check passed" in check_result.stdout


def _windows_powershell_path(
    environ: dict[str, str], platform: str
) -> Path | None:
    system_root = environ.get("SystemRoot")
    if platform != "nt":
        return None
    if system_root:
        candidate = (
            Path(system_root)
            / "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        if candidate.is_file():
            return candidate
    discovered = shutil.which("powershell")
    return None if discovered is None else Path(discovered)


def test_powershell_probe_is_safe_without_windows_environment() -> None:
    assert _windows_powershell_path({}, "posix") is None


def test_powershell_clean_room_script_parses_its_default_source_root() -> None:
    powershell = _windows_powershell_path(dict(os.environ), os.name)
    if powershell is None:
        pytest.skip("Windows PowerShell semantics are unavailable")
    environment = os.environ.copy()
    environment["PATH"] = ""
    completed = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/clean_room_audit.ps1"),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert f"+ git clone --no-local {ROOT} " in completed.stdout
    assert "Cannot bind argument to parameter 'Path'" not in completed.stderr


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_public_assets_regenerate_without_a_diff() -> None:
    asset_root = ROOT / "docs" / "assets"

    def asset_snapshot() -> dict[str, bytes]:
        return {
            path.relative_to(ROOT).as_posix(): path.read_bytes()
            for path in sorted(asset_root.rglob("*"))
            if path.is_file()
        }

    assets_before = asset_snapshot()
    commands = [
        [
            "python",
            "-m",
            "voice_replication_kit.corpus",
            "--source",
            "corpus/recording-script.json",
            "--output-dir",
            "corpus",
        ],
        [
            "python",
            "tools/build_scorecard.py",
            "--check",
            "evaluation/voice-evaluation-scorecard.xlsx",
        ],
        ["python", "tools/build_diagrams.py", "--check"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            "--",
            "corpus",
            "evaluation/voice-evaluation-scorecard.xlsx",
        ],
        cwd=ROOT,
        check=True,
    )
    assert asset_snapshot() == assets_before
    generated_corpus = [
        path
        for path in git_lines(ROOT, "ls-files", "corpus")
        if path != "corpus/recording-script.json"
    ]
    for relative in generated_corpus:
        staged = subprocess.run(
            ["git", "show", f":{relative}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert (ROOT / relative).read_bytes() == staged, relative


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_no_tracked_path_uses_a_private_capable_name_or_extension() -> None:
    tracked = git_lines(ROOT, "ls-files")
    forbidden = []
    for raw in tracked:
        path = PurePosixPath(raw)
        if path.name.lower() in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            forbidden.append(raw)
    assert forbidden == []


@pytest.mark.skipif(
    not _is_repository_git_worktree(), reason="requires the repository Git worktree"
)
def test_reachable_commit_identities_are_public_noreply() -> None:
    rows = git_lines(ROOT, "log", "--all", "--format=%an%x09%ae%x09%cn%x09%ce")
    approved = (PUBLIC_NAME, PUBLIC_EMAIL, PUBLIC_NAME, PUBLIC_EMAIL)

    assert rows
    for row in rows:
        assert tuple(row.split("\t")) == approved
