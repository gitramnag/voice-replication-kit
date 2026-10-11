"""Verification gates for the pinned CosyVoice runtime and generic model."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import builtins
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any
from urllib.parse import urlsplit

from voice_replication_kit.errors import UserValidationError as ValueError


_BuiltinValueError = builtins.ValueError


_COMMIT = re.compile(r"[0-9a-f]{40}")
_HASH = re.compile(r"[0-9a-f]{64}")
_PIN = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_.,-]+\])?)"
    r"==(?P<version>[^\s;\\]+)(?:\s*;.+)?$"
)
_LOCK_DIRECTIVES = (
    "--extra-index-url https://download.pytorch.org/whl/cu121",
    "--extra-index-url https://aiinfra.pkgs.visualstudio.com/"
    "PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/",
)


class RuntimeVerificationError(ValueError):
    """Raised when immutable runtime provenance does not match its review."""


def _read_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeVerificationError(f"cannot read {description}: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeVerificationError(f"{description} must be a JSON object")
    return value


def _immutable_commit(value: object, description: str) -> str:
    if not isinstance(value, str) or _COMMIT.fullmatch(value) is None:
        raise RuntimeVerificationError(
            f"{description} must be 40 lowercase hex characters"
        )
    return value


def load_runtime_pins(path: Path) -> dict[str, Any]:
    """Load and validate the public immutable source and model pins."""
    pins = _read_json_object(path, "runtime pins")
    if pins.get("schema_version") != 1 or pins.get("python") != "3.10":
        raise RuntimeVerificationError("runtime pins require schema 1 and Python 3.10")
    sources = pins.get("sources")
    if not isinstance(sources, Mapping) or not sources:
        raise RuntimeVerificationError("runtime pins must contain sources")
    for name, raw_source in sources.items():
        if not isinstance(name, str) or not isinstance(raw_source, Mapping):
            raise RuntimeVerificationError("each source pin must be an object")
        url = raw_source.get("url")
        if not isinstance(url, str):
            raise RuntimeVerificationError(f"source {name} URL must use HTTPS")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username:
            raise RuntimeVerificationError(f"source {name} URL must use HTTPS")
        _immutable_commit(raw_source.get("commit"), f"source {name} commit")
    model = pins.get("model")
    if not isinstance(model, Mapping) or not isinstance(
        model.get("repository"), str
    ):
        raise RuntimeVerificationError("runtime pins must contain a model repository")
    _immutable_commit(model.get("revision"), "model revision")
    return pins


def _git_text(path: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeVerificationError(f"cannot inspect source checkout: {path}") from error
    if result.returncode != 0:
        raise RuntimeVerificationError(f"cannot inspect source checkout: {path}")
    return result.stdout.strip()


def _git_bytes(path: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise RuntimeVerificationError(
            f"cannot inspect source checkout: {path}"
        ) from error
    if result.returncode != 0:
        raise RuntimeVerificationError(f"cannot inspect source checkout: {path}")
    return result.stdout


def _normalise_git_url(value: str) -> str:
    return value.rstrip("/")


def verify_source_checkout(
    path: Path, expected_remote: str, expected_commit: str
) -> None:
    """Require one checkout to match its exact reviewed origin and Git head."""
    _immutable_commit(expected_commit, "source commit")
    actual_remote = _git_text(path, "remote", "get-url", "origin")
    if _normalise_git_url(actual_remote) != _normalise_git_url(expected_remote):
        raise RuntimeVerificationError("source checkout does not match pinned origin")
    actual_head = _git_text(path, "rev-parse", "HEAD")
    if actual_head != expected_commit:
        raise RuntimeVerificationError("source checkout does not match pinned HEAD")
    status = _git_text(path, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise RuntimeVerificationError("source checkout must have a clean worktree")
    ignored = _git_bytes(
        path, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"
    )
    source_suffixes = {
        ".c", ".cc", ".cpp", ".cu", ".cuh", ".dll", ".dylib", ".h",
        ".hpp", ".js", ".pyc", ".pyd", ".py", ".pyi", ".pyo", ".sh",
        ".so", ".ts",
    }
    ignored_paths = [
        PurePosixPath(raw.decode("utf-8", "surrogateescape"))
        for raw in ignored.split(b"\0")
        if raw
    ]
    if any(
        candidate.suffix.casefold() in source_suffixes
        for candidate in ignored_paths
    ):
        raise RuntimeVerificationError("source checkout must have a clean worktree")


def _logical_lock_lines(path: Path) -> list[str]:
    try:
        physical_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeVerificationError(f"cannot read runtime lock: {path}") from error
    logical_lines: list[str] = []
    pending = ""
    for raw_line in physical_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        continued = stripped.endswith("\\")
        part = stripped[:-1].rstrip() if continued else stripped
        pending = f"{pending} {part}".strip()
        if not continued:
            logical_lines.append(pending)
            pending = ""
    if pending:
        raise RuntimeVerificationError("runtime lock has an incomplete continuation")
    return logical_lines


def verify_runtime_lock(path: Path) -> tuple[str, ...]:
    """Return lock entries after requiring exact versions and SHA-256 hashes."""
    requirements: list[str] = []
    directives: list[str] = []
    for line in _logical_lock_lines(path):
        if line in _LOCK_DIRECTIVES:
            directives.append(line)
            continue
        if line.startswith("-") or "://" in line or " @ " in line:
            raise RuntimeVerificationError(
                f"unsupported runtime lock directive: {line.split()[0]}"
            )
        requirement, separator, _hashes = line.partition(" --hash=")
        match = _PIN.fullmatch(requirement)
        if match is None:
            raise RuntimeVerificationError(
                f"runtime requirement is not exactly pinned: {line.split()[0]}"
            )
        hashes = re.findall(r"--hash=sha256:([0-9a-f]+)", line)
        if not separator or not hashes or any(
            _HASH.fullmatch(value) is None for value in hashes
        ):
            raise RuntimeVerificationError(
                f"runtime requirement lacks a valid sha256 hash: {match.group('name')}"
            )
        requirements.append(requirement)
    if tuple(directives) != _LOCK_DIRECTIVES:
        raise RuntimeVerificationError("runtime lock must use the exact reviewed indexes")
    if not requirements:
        raise RuntimeVerificationError("runtime lock contains no requirements")
    return tuple(requirements)


def _safe_model_path(model_root: Path, raw_path: object) -> tuple[str, Path]:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        raise RuntimeVerificationError("model path escapes snapshot root")
    relative = PurePosixPath(raw_path)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise RuntimeVerificationError(f"model path escapes snapshot root: {raw_path}")
    root = model_root.resolve(strict=False)
    candidate = (root / Path(*relative.parts)).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except _BuiltinValueError as error:
        raise RuntimeVerificationError(
            f"model path escapes snapshot root: {raw_path}"
        ) from error
    return relative.as_posix(), candidate


def _file_digest(path: Path, algorithm: str, size: int) -> str:
    digest = hashlib.new(algorithm)
    if algorithm == "sha1":
        digest.update(b"blob " + str(size).encode("ascii") + b"\0")
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_snapshot(model_root: Path, manifest: Mapping[str, Any]) -> None:
    """Verify the model tree is exactly the reviewed file set and digests."""
    files = manifest.get("files")
    if not isinstance(files, Sequence) or isinstance(files, (str, bytes)):
        raise RuntimeVerificationError("model manifest files must be an array")
    expected: set[str] = set()
    for raw_entry in files:
        if not isinstance(raw_entry, Mapping):
            raise RuntimeVerificationError("model manifest entry must be an object")
        display_path, path = _safe_model_path(model_root, raw_entry.get("path"))
        if display_path in expected:
            raise RuntimeVerificationError(f"duplicate model file: {display_path}")
        expected.add(display_path)
        size = raw_entry.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise RuntimeVerificationError(f"invalid model size: {display_path}")
        if not path.is_file() or path.is_symlink() or path.stat().st_size != size:
            raise RuntimeVerificationError(f"model file mismatch: {display_path}")
        digest_fields = [
            field for field in ("sha256", "git_sha1") if field in raw_entry
        ]
        if len(digest_fields) != 1:
            raise RuntimeVerificationError(f"invalid model digest: {display_path}")
        field = digest_fields[0]
        value = raw_entry[field]
        expected_pattern = _HASH if field == "sha256" else _COMMIT
        if not isinstance(value, str) or expected_pattern.fullmatch(value) is None:
            raise RuntimeVerificationError(f"invalid model digest: {display_path}")
        algorithm = "sha256" if field == "sha256" else "sha1"
        if _file_digest(path, algorithm, size) != value:
            raise RuntimeVerificationError(f"model digest mismatch: {display_path}")

    root = model_root.resolve(strict=False)
    if not root.is_dir():
        raise RuntimeVerificationError(f"model snapshot is not a directory: {model_root}")
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeVerificationError(f"model snapshot contains symlink: {path.name}")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    unexpected = sorted(actual - expected)
    if unexpected:
        raise RuntimeVerificationError(f"unexpected model file: {unexpected[0]}")
    missing = sorted(expected - actual)
    if missing:
        raise RuntimeVerificationError(f"missing model file: {missing[0]}")


def runtime_provenance(private_root: Path) -> dict[str, Any]:
    """Read the bootstrap record kept beneath the external private root."""
    return _read_json_object(
        private_root / "runtime" / "provenance.json", "runtime provenance"
    )
