"""Byte-accurate file sources for publication audits."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Iterator


_FALLBACK_SKIPPED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".superpowers",
    ".venv",
    "__pycache__",
}


class AuditSourceError(RuntimeError):
    """A Git-backed audit source could not be read safely."""


@dataclass(frozen=True)
class AuditEntry:
    """One path and the exact bytes selected for an audit."""

    path: PurePosixPath
    data: bytes
    source: str
    object_id: str | None = None


@dataclass(frozen=True)
class GitProbe:
    """Raw result from the repository-discovery command."""

    returncode: int
    stdout: bytes
    stderr: bytes


def _run_git(root: Path, *arguments: str, input_data: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            input=input_data,
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise AuditSourceError("Git is unavailable for publication audit") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise AuditSourceError(detail or "Git could not read publication audit data")
    return result.stdout


def _probe_git(
    root: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> GitProbe:
    try:
        result = runner(
            ["git", "rev-parse", "--is-inside-work-tree", "--show-toplevel"],
            cwd=root,
            check=False,
            capture_output=True,
            env={**os.environ, "LANG": "C", "LC_ALL": "C"},
        )
    except OSError as error:
        raise AuditSourceError("Git is unavailable for publication audit") from error
    return GitProbe(result.returncode, result.stdout, result.stderr)


def _has_git_marker(root: Path) -> bool:
    return any((candidate / ".git").exists() for candidate in (root, *root.parents))


def _classify_git_probe(root: Path, probe: GitProbe) -> Path | None:
    if probe.returncode != 0:
        detail = probe.stderr.decode("utf-8", "replace").strip()
        if not _has_git_marker(root) and "not a git repository" in detail.lower():
            return None
        raise AuditSourceError(
            f"Git repository probe failed: {detail or 'no diagnostic output'}"
        )

    lines = probe.stdout.splitlines()
    if probe.stderr.strip() or len(lines) != 2 or lines[0] != b"true" or not lines[1]:
        raise AuditSourceError("unexpected Git repository probe output")
    repository = Path(_decode_path(lines[1])).resolve()
    if not repository.is_dir():
        raise AuditSourceError("unexpected Git repository probe output")
    try:
        root.relative_to(repository)
    except ValueError as error:
        raise AuditSourceError("unexpected Git repository probe output") from error
    return repository


def _repository_root(root: Path) -> Path | None:
    return _classify_git_probe(root, _probe_git(root))


def _require_git_worktree(root: Path) -> Path:
    repository = _repository_root(root)
    if repository is None:
        raise AuditSourceError("audit mode requires a Git worktree")
    return repository


def _decode_path(path: bytes) -> str:
    return path.decode("utf-8", "surrogateescape")


def _split_nul_records(output: bytes, description: str) -> list[bytes]:
    if not output:
        return []
    if not output.endswith(b"\0"):
        raise AuditSourceError(f"malformed NUL-delimited {description} output")
    records = output[:-1].split(b"\0")
    if any(not record for record in records):
        raise AuditSourceError(f"malformed NUL-delimited {description} output")
    return records


def _parse_tree_paths(output: bytes) -> list[PurePosixPath]:
    return [
        PurePosixPath(_decode_path(record))
        for record in _split_nul_records(output, "tree")
    ]


def _filesystem_tree_paths(root: Path) -> Iterator[PurePosixPath]:

    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in _FALLBACK_SKIPPED_DIRECTORIES for part in relative.parts):
            continue
        if path.is_file():
            yield PurePosixPath(relative.as_posix())


def tree_entries(root: Path) -> Iterator[AuditEntry]:
    """Yield candidate public paths with their current working-tree bytes."""
    root = Path(root).resolve()
    repository = _repository_root(root)
    if repository is None:
        scan_root = root
        paths: Iterator[PurePosixPath] = _filesystem_tree_paths(root)
    else:
        scan_root = repository
        paths = iter(
            _parse_tree_paths(
                _run_git(
                    repository,
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "-z",
                )
            )
        )
    try:
        for relative in paths:
            path = scan_root.joinpath(*relative.parts)
            if path.is_symlink():
                data = str(path.readlink()).encode("utf-8", "surrogateescape")
                yield AuditEntry(relative, data, "tree")
            elif path.is_file():
                yield AuditEntry(relative, path.read_bytes(), "tree")
    except OSError as error:
        raise AuditSourceError("could not read working-tree audit bytes") from error


def ignored_paths(root: Path) -> Iterator[PurePosixPath]:
    """Yield ignored untracked path names without reading their contents."""
    root = Path(root).resolve()
    repository = _repository_root(root)
    if repository is None:
        return
    output = _run_git(
        repository,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "-z",
    )
    yield from _parse_tree_paths(output)


def _parse_index(output: bytes) -> list[tuple[PurePosixPath, str]]:
    parsed: list[tuple[PurePosixPath, str]] = []
    for record in _split_nul_records(output, "index"):
        try:
            metadata, path_bytes = record.split(b"\t", 1)
            _mode, object_id_bytes, stage = metadata.split()
            object_id = object_id_bytes.decode("ascii")
        except (UnicodeDecodeError, ValueError) as error:
            raise AuditSourceError("Git returned a malformed index entry") from error
        if stage != b"0":
            raise AuditSourceError("resolve unmerged index entries before auditing")
        parsed.append((PurePosixPath(_decode_path(path_bytes)), object_id))
    return parsed


def index_entries(root: Path) -> Iterator[AuditEntry]:
    """Yield stage-zero index paths with bytes read from their blob objects."""
    root = Path(root).resolve()
    repository = _require_git_worktree(root)
    entries = _parse_index(_run_git(repository, "ls-files", "-s", "-z"))
    for path, object_id in entries:
        data = _run_git(repository, "cat-file", "blob", object_id)
        yield AuditEntry(path, data, "index", object_id)


def _parse_history_tree(output: bytes) -> list[tuple[PurePosixPath, str]]:
    parsed: list[tuple[PurePosixPath, str]] = []
    for record in _split_nul_records(output, "history tree"):
        try:
            metadata, path_bytes = record.split(b"\t", 1)
            _mode, object_type, object_id_bytes = metadata.split()
            object_id = object_id_bytes.decode("ascii")
        except (UnicodeDecodeError, ValueError) as error:
            raise AuditSourceError("Git returned a malformed tree entry") from error
        if object_type == b"blob":
            parsed.append((PurePosixPath(_decode_path(path_bytes)), object_id))
    return parsed


def _history_commit_ids(repository: Path) -> list[str]:
    commits: list[str] = []
    for commit in _run_git(repository, "rev-list", "--all").splitlines():
        try:
            commits.append(commit.decode("ascii"))
        except UnicodeDecodeError as error:
            raise AuditSourceError("Git returned a malformed commit ID") from error
    return commits


def _history_pairs(
    repository: Path, commits: list[str]
) -> list[tuple[PurePosixPath, str]]:
    seen: set[tuple[str, bytes]] = set()
    pairs: list[tuple[PurePosixPath, str]] = []
    for commit_id in commits:
        output = _run_git(
            repository, "ls-tree", "-r", "-z", "--full-tree", commit_id
        )
        for path, object_id in _parse_history_tree(output):
            key = (object_id, str(path).encode("utf-8", "surrogateescape"))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((path, object_id))
    return pairs


def _cat_file_batch(root: Path, object_ids: list[str]) -> dict[str, bytes]:
    unique_ids = list(dict.fromkeys(object_ids))
    if not unique_ids:
        return {}
    output = _run_git(
        root,
        "cat-file",
        "--batch",
        input_data=b"".join(object_id.encode("ascii") + b"\n" for object_id in unique_ids),
    )
    blobs: dict[str, bytes] = {}
    offset = 0
    for requested_id in unique_ids:
        header_end = output.find(b"\n", offset)
        if header_end < 0:
            raise AuditSourceError("Git returned a truncated blob header")
        header = output[offset:header_end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise AuditSourceError("Git returned a non-blob history object")
        try:
            returned_id = header[0].decode("ascii")
            size = int(header[2])
        except (UnicodeDecodeError, ValueError) as error:
            raise AuditSourceError("Git returned a malformed blob header") from error
        data_start = header_end + 1
        data_end = data_start + size
        if data_end >= len(output) or output[data_end : data_end + 1] != b"\n":
            raise AuditSourceError("Git returned truncated blob bytes")
        if returned_id != requested_id:
            raise AuditSourceError("Git returned history blobs out of order")
        blobs[requested_id] = output[data_start:data_end]
        offset = data_end + 1
    if offset != len(output):
        raise AuditSourceError("Git returned unexpected trailing blob bytes")
    return blobs


def history_entries(root: Path) -> Iterator[AuditEntry]:
    """Yield reachable commit bytes and unique historical blob/path pairs."""
    root = Path(root).resolve()
    repository = _require_git_worktree(root)
    commits = _history_commit_ids(repository)
    for commit_id in commits:
        data = _run_git(repository, "cat-file", "commit", commit_id)
        yield AuditEntry(
            PurePosixPath(f".git-history/{commit_id}.commit"),
            data,
            "history",
            commit_id,
        )
    pairs = _history_pairs(repository, commits)
    blobs = _cat_file_batch(
        repository, [object_id for _path, object_id in pairs]
    )
    for path, object_id in pairs:
        yield AuditEntry(path, blobs[object_id], "history", object_id)
