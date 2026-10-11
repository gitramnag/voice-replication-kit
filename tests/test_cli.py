from __future__ import annotations

import subprocess
import sys
import sysconfig
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _init_approved_git(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "gitramnag"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "315322897+gitramnag@users.noreply.github.com",
        ],
        cwd=root,
        check=True,
    )


def _run_script(name: str, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), "--root", str(root), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def _run_voice_kit(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    scripts = Path(sysconfig.get_path("scripts"))
    command = next(
        candidate
        for candidate in (scripts / "voice-kit.exe", scripts / "voice-kit")
        if candidate.is_file()
    )
    return subprocess.run(
        [str(command), "audit", "--root", str(root), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_publication_cli_returns_zero_for_a_safe_tree(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Safe\n", encoding="utf-8")

    completed = _run_script("check_publication.py", tmp_path)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "publication boundary check passed"


def test_publication_cli_returns_one_for_forbidden_audio(tmp_path: Path) -> None:
    (tmp_path / "candidate.wav").write_bytes(b"not real audio")

    completed = _run_script("check_publication.py", tmp_path)

    assert completed.returncode == 1
    assert "forbidden-extension: candidate.wav" in completed.stdout


def test_publication_cli_rejects_a_missing_root(tmp_path: Path) -> None:
    completed = _run_script("check_publication.py", tmp_path / "missing")

    assert completed.returncode == 2
    assert completed.stdout.strip() == "repository root is not a directory"


def test_publication_cli_staged_mode_ignores_unstaged_findings(
    tmp_path: Path,
) -> None:
    _init_approved_git(tmp_path)
    (tmp_path / "README.md").write_text("# Safe\n", encoding="utf-8")
    (tmp_path / "candidate.wav").write_bytes(b"not real audio")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)

    completed = _run_script("check_publication.py", tmp_path, "--staged")

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "publication boundary check passed"


def test_publication_cli_staged_mode_requires_a_git_worktree(tmp_path: Path) -> None:
    completed = _run_script("check_publication.py", tmp_path, "--staged")

    assert completed.returncode == 2
    assert completed.stdout.strip() == "staged scan requires a Git worktree"


def test_publication_cli_staged_mode_rejects_staged_audio(tmp_path: Path) -> None:
    _init_approved_git(tmp_path)
    (tmp_path / "candidate.wav").write_bytes(b"not real audio")
    subprocess.run(["git", "add", "candidate.wav"], cwd=tmp_path, check=True)

    completed = _run_script("check_publication.py", tmp_path, "--staged")

    assert completed.returncode == 1
    assert "forbidden-extension: candidate.wav" in completed.stdout


def test_publication_cli_staged_mode_reads_index_bytes(tmp_path: Path) -> None:
    _init_approved_git(tmp_path)
    path = tmp_path / "notes.md"
    path.write_text("Safe staged bytes.\n", encoding="utf-8")
    subprocess.run(["git", "add", "notes.md"], cwd=tmp_path, check=True)
    path.write_text(
        "Run C:\\" + "Users\\PrivatePerson\\voice\\render.py\n", encoding="utf-8"
    )

    completed = _run_script("check_publication.py", tmp_path, "--mode", "staged")

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "publication boundary check passed"


def test_publication_cli_history_mode_finds_deleted_audio(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test" + "@" + "example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "removed.wav").write_bytes(b"private")
    subprocess.run(["git", "add", "removed.wav"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=tmp_path, check=True)
    subprocess.run(["git", "rm", "-q", "removed.wav"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "remove"], cwd=tmp_path, check=True
    )

    completed = _run_script("check_publication.py", tmp_path, "--mode", "history")

    assert completed.returncode == 1
    assert "forbidden-extension: removed.wav" in completed.stdout


def test_voice_kit_audit_staged_uses_the_shared_index_engine(tmp_path: Path) -> None:
    _init_approved_git(tmp_path)
    path = tmp_path / "notes.md"
    path.write_text("Safe staged bytes.\n", encoding="utf-8")
    subprocess.run(["git", "add", "notes.md"], cwd=tmp_path, check=True)
    path.write_text(
        "Run C:\\" + "Users\\PrivatePerson\\voice\\render.py\n", encoding="utf-8"
    )

    completed = _run_voice_kit(tmp_path, "--mode", "staged")

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "publication boundary check passed"


def test_voice_kit_nested_root_still_finds_staged_repository_path(
    tmp_path: Path,
) -> None:
    _init_approved_git(tmp_path)
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / "inside.md").write_text("Safe.\n", encoding="utf-8")
    (tmp_path / "outside.wav").write_bytes(b"private")
    subprocess.run(
        ["git", "add", "src/inside.md", "outside.wav"], cwd=tmp_path, check=True
    )

    completed = _run_voice_kit(nested, "--mode", "staged")

    assert completed.returncode == 1
    assert "forbidden-extension: outside.wav" in completed.stdout


def test_voice_kit_audit_uses_external_private_terms_without_echoing_them(
    tmp_path: Path,
) -> None:
    private_term = "Confidential Zephyr"
    terms = tmp_path.parent / f"{tmp_path.name}-owner-terms.txt"
    terms.write_text(private_term + "\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text(
        private_term.lower() + "\n", encoding="utf-8"
    )

    completed = _run_voice_kit(
        tmp_path, "--private-terms-file", str(terms)
    )

    assert completed.returncode == 1
    assert "private-term-content: notes.md" in completed.stdout
    assert private_term.casefold() not in completed.stdout.casefold()


def test_link_cli_accepts_relative_targets_fragments_and_external_urls(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text(
        "[Run it](docs/guide.md#run-it)\n[Website](https://example.com)\n",
        encoding="utf-8",
    )
    (docs / "guide.md").write_text("# Guide\n\n## Run it\n", encoding="utf-8")

    completed = _run_script("check_links.py", tmp_path)

    assert completed.returncode == 0, completed.stdout
    assert completed.stdout.strip() == "link check passed (2 Markdown files, 1 local link)"


def test_link_cli_accepts_reference_style_links(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text(
        "Read the [guide][setup].\n\n[setup]: docs/guide.md#install\n",
        encoding="utf-8",
    )
    (docs / "guide.md").write_text("# Guide\n\n## Install\n", encoding="utf-8")

    completed = _run_script("check_links.py", tmp_path)

    assert completed.returncode == 0, completed.stdout
    assert completed.stdout.strip() == "link check passed (2 Markdown files, 1 local link)"


def test_link_cli_reports_a_missing_target(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "[Missing](docs/missing.md)\n", encoding="utf-8"
    )

    completed = _run_script("check_links.py", tmp_path)

    assert completed.returncode == 1
    assert "README.md:1: missing target: docs/missing.md" in completed.stdout


def test_link_cli_rejects_a_missing_root(tmp_path: Path) -> None:
    completed = _run_script("check_links.py", tmp_path / "missing")

    assert completed.returncode == 2
    assert completed.stdout.strip() == "repository root is not a directory"


def test_link_cli_reports_a_missing_heading_fragment(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "[Missing heading](guide.md#absent)\n", encoding="utf-8"
    )
    (tmp_path / "guide.md").write_text("# Present\n", encoding="utf-8")

    completed = _run_script("check_links.py", tmp_path)

    assert completed.returncode == 1
    assert "README.md:1: missing heading: guide.md#absent" in completed.stdout


def test_link_cli_rejects_a_target_outside_the_root(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Outside](../outside.md)\n", encoding="utf-8")

    completed = _run_script("check_links.py", tmp_path)

    assert completed.returncode == 1
    assert "README.md:1: target escapes root: ../outside.md" in completed.stdout
