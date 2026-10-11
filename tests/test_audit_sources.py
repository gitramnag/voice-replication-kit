from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path, PurePosixPath
import subprocess

import pytest

from voice_replication_kit.audit_sources import (
    AuditEntry,
    AuditSourceError,
    GitProbe,
    _classify_git_probe,
    _parse_history_tree,
    _parse_index,
    _parse_tree_paths,
    _probe_git,
    history_entries,
    index_entries,
    tree_entries,
)


def git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=check,
        capture_output=True,
    )


def initialise_git(root: Path) -> None:
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "gitramnag")
    git(
        root,
        "config",
        "user.email",
        "315322897+gitramnag@users.noreply.github.com",
    )


def commit_file(root: Path, relative: str, data: bytes, message: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    git(root, "add", "--", relative)
    git(root, "commit", "-q", "-m", message)


def test_audit_entry_is_immutable() -> None:
    entry = AuditEntry(PurePosixPath("notes.md"), b"safe\n", "tree")

    with pytest.raises(FrozenInstanceError):
        entry.source = "index"  # type: ignore[misc]


def test_tree_scan_reads_tracked_and_non_ignored_worktree_bytes(tmp_path: Path) -> None:
    initialise_git(tmp_path)
    commit_file(tmp_path, "tracked.md", b"committed bytes\n", "add tracked")
    (tmp_path / "tracked.md").write_bytes(b"working tree bytes\n")
    (tmp_path / "untracked.md").write_bytes(b"untracked bytes\n")
    (tmp_path / ".gitignore").write_text(
        ".superpowers/\n*.cache\n", encoding="utf-8"
    )
    (tmp_path / ".superpowers").mkdir()
    (tmp_path / ".superpowers" / "evidence.wav").write_bytes(b"private evidence")
    (tmp_path / "ignored.cache").write_bytes(b"private cache")

    entries = {entry.path.as_posix(): entry for entry in tree_entries(tmp_path)}

    assert entries["tracked.md"].data == b"working tree bytes\n"
    assert entries["untracked.md"].data == b"untracked bytes\n"
    assert ".gitignore" in entries
    assert ".superpowers/evidence.wav" not in entries
    assert "ignored.cache" not in entries
    assert not any(path.startswith(".git/") for path in entries)


def test_nested_root_keeps_repository_relative_paths_for_all_git_sources(
    tmp_path: Path,
) -> None:
    initialise_git(tmp_path)
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / "inside.md").write_bytes(b"inside\n")
    (tmp_path / "outside.wav").write_bytes(b"outside\n")
    git(tmp_path, "add", "src/inside.md", "outside.wav")
    git(tmp_path, "commit", "-q", "-m", "add candidates")

    for entries in (tree_entries(nested), index_entries(nested)):
        assert {entry.path.as_posix() for entry in entries} == {
            "outside.wav",
            "src/inside.md",
        }
    history_paths = {entry.path.as_posix() for entry in history_entries(nested)}
    assert {"outside.wav", "src/inside.md"} < history_paths
    assert len(
        {
            path
            for path in history_paths
            if path.startswith(".git-history/") and path.endswith(".commit")
        }
    ) == 1


@pytest.mark.parametrize(
    ("parser", "record"),
    [
        (_parse_tree_paths, b"notes.md"),
        (_parse_index, b"100644 0123456789012345678901234567890123456789 0\tnotes.md"),
        (
            _parse_history_tree,
            b"100644 blob 0123456789012345678901234567890123456789\tnotes.md",
        ),
    ],
)
@pytest.mark.parametrize("malformation", ["unterminated", "embedded-empty"])
def test_git_nul_record_parsers_reject_malformed_framing(
    parser: object, record: bytes, malformation: str
) -> None:
    output = (
        record
        if malformation == "unterminated"
        else record + b"\0\0" + record + b"\0"
    )

    with pytest.raises(AuditSourceError, match="malformed NUL-delimited"):
        parser(output)  # type: ignore[operator]


@pytest.mark.parametrize("parser", [_parse_tree_paths, _parse_index, _parse_history_tree])
def test_git_nul_record_parsers_accept_empty_output(parser: object) -> None:
    assert parser(b"") == []  # type: ignore[operator]


def test_probe_classifies_real_non_git_directory_for_fallback(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_bytes(b"safe\n")

    assert list(tree_entries(tmp_path)) == [
        AuditEntry(PurePosixPath("notes.md"), b"safe\n", "tree")
    ]


@pytest.mark.parametrize(
    "stderr",
    [
        b"fatal: detected dubious ownership in repository\n",
        b"fatal: bad config line 1 in file config\n",
        b"fatal: unknown repository error\n",
    ],
)
def test_probe_classification_fails_closed_for_git_errors(
    tmp_path: Path, stderr: bytes
) -> None:
    with pytest.raises(AuditSourceError, match="Git repository probe failed"):
        _classify_git_probe(tmp_path, GitProbe(128, b"", stderr))


def test_probe_classification_does_not_hide_corrupt_git_marker(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    probe = GitProbe(
        128,
        b"",
        b"fatal: not a git repository (or any of the parent directories): .git\n",
    )

    with pytest.raises(AuditSourceError, match="Git repository probe failed"):
        _classify_git_probe(tmp_path, probe)


@pytest.mark.parametrize(
    "stdout",
    [
        b"maybe\nC:/repository\n",
        b"true\n",
        b"true\nC:/repository\nextra\n",
    ],
)
def test_probe_classification_rejects_unexpected_success_output(
    tmp_path: Path, stdout: bytes
) -> None:
    with pytest.raises(AuditSourceError, match="unexpected Git repository probe output"):
        _classify_git_probe(tmp_path, GitProbe(0, stdout, b""))


def test_probe_reports_missing_git_as_source_error(tmp_path: Path) -> None:
    def missing_git(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("git")

    with pytest.raises(AuditSourceError, match="Git is unavailable"):
        _probe_git(tmp_path, runner=missing_git)


def test_staged_scan_reads_index_blob_not_worktree(tmp_path: Path) -> None:
    initialise_git(tmp_path)
    path = tmp_path / "notes.md"
    path.write_text("safe staged bytes\n", encoding="utf-8")
    git(tmp_path, "add", "notes.md")
    path.write_text(
        "Run C:\\" + "Users\\PrivatePerson\\voice\\render.py\n", encoding="utf-8"
    )

    entries = list(index_entries(tmp_path))

    assert len(entries) == 1
    assert entries[0].path == PurePosixPath("notes.md")
    assert entries[0].data == b"safe staged bytes\n"
    assert entries[0].source == "index"
    assert entries[0].object_id == git(
        tmp_path, "rev-parse", ":notes.md"
    ).stdout.decode("ascii").strip()


def test_index_scan_preserves_spaces_and_non_ascii_paths(tmp_path: Path) -> None:
    initialise_git(tmp_path)
    relative = "notes/voice sample 日本語.md"
    data = b"exact staged bytes\x00\xff"
    path = tmp_path / relative
    path.parent.mkdir()
    path.write_bytes(data)
    git(tmp_path, "add", "--", relative)

    entries = list(index_entries(tmp_path))

    assert [(entry.path.as_posix(), entry.data) for entry in entries] == [
        (relative, b"exact staged bytes\x00\xff")
    ]


def test_history_scan_preserves_tab_in_nul_delimited_tree_path(tmp_path: Path) -> None:
    initialise_git(tmp_path)
    relative = "voice sample\t日本語.md"
    data = b"historical bytes"
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=tmp_path,
        input=data,
        check=True,
        capture_output=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "mktree", "-z"],
        cwd=tmp_path,
        input=b"100644 blob " + blob + b"\t" + relative.encode("utf-8") + b"\0",
        check=True,
        capture_output=True,
    ).stdout.strip()
    commit = subprocess.run(
        ["git", "commit-tree", tree.decode("ascii"), "-m", "raw path"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    ).stdout.strip()
    git(tmp_path, "update-ref", "refs/heads/main", commit.decode("ascii"))

    entries = [
        entry for entry in history_entries(tmp_path) if entry.path == PurePosixPath(relative)
    ]

    assert [(entry.path.as_posix(), entry.data) for entry in entries] == [
        (relative, data)
    ]


def test_index_scan_fails_closed_on_unmerged_entries(tmp_path: Path) -> None:
    initialise_git(tmp_path)
    commit_file(tmp_path, "conflict.txt", b"base\n", "base")
    git(tmp_path, "checkout", "-q", "-b", "topic")
    commit_file(tmp_path, "conflict.txt", b"topic\n", "topic")
    git(tmp_path, "checkout", "-q", "main")
    commit_file(tmp_path, "conflict.txt", b"main\n", "main")
    merge = git(tmp_path, "merge", "topic", check=False)
    assert merge.returncode != 0

    with pytest.raises(
        AuditSourceError, match="resolve unmerged index entries before auditing"
    ):
        list(index_entries(tmp_path))


def test_history_scan_reads_deleted_reachable_blob(tmp_path: Path) -> None:
    initialise_git(tmp_path)
    commit_file(tmp_path, "removed.env", b"SECRET_KEY=private\n", "add secret")
    git(tmp_path, "rm", "-q", "removed.env")
    git(tmp_path, "commit", "-q", "-m", "remove secret")
    expected_id = git(tmp_path, "rev-parse", "HEAD^:removed.env").stdout.decode(
        "ascii"
    ).strip()

    entries = list(history_entries(tmp_path))

    assert any(
        entry.path.as_posix() == "removed.env"
        and entry.data == b"SECRET_KEY=private\n"
        and entry.object_id == expected_id
        for entry in entries
    )


def test_history_scan_reads_reachable_commit_objects(tmp_path: Path) -> None:
    initialise_git(tmp_path)
    commit_file(
        tmp_path,
        "safe.md",
        b"safe bytes\n",
        "record C:" + r"\Users\PrivatePerson\voice\render.py",
    )
    commit_id = git(tmp_path, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    commit_bytes = git(tmp_path, "cat-file", "commit", commit_id).stdout

    commit_entries = [
        entry for entry in history_entries(tmp_path) if entry.path.suffix == ".commit"
    ]

    assert commit_entries == [
        AuditEntry(
            PurePosixPath(f".git-history/{commit_id}.commit"),
            commit_bytes,
            "history",
            commit_id,
        )
    ]


def test_history_scan_evaluates_renamed_blob_under_each_historical_path(
    tmp_path: Path,
) -> None:
    initialise_git(tmp_path)
    commit_file(tmp_path, "first name.md", b"same bytes\n", "add first name")
    git(tmp_path, "mv", "first name.md", "renamed name.md")
    git(tmp_path, "commit", "-q", "-m", "rename file")
    expected_id = git(tmp_path, "rev-parse", "HEAD:renamed name.md").stdout.decode(
        "ascii"
    ).strip()

    entries = [
        entry for entry in history_entries(tmp_path) if entry.data == b"same bytes\n"
    ]

    assert [(entry.path.as_posix(), entry.object_id) for entry in entries] == [
        ("renamed name.md", expected_id),
        ("first name.md", expected_id),
    ]
