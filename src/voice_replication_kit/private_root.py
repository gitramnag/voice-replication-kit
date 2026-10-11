"""Resolve and initialise the external private voice workspace."""

from collections.abc import Mapping
import builtins
import json
from pathlib import Path

from voice_replication_kit.errors import UserValidationError as ValueError


_BuiltinValueError = builtins.ValueError


PRIVATE_DIRECTORIES = (
    Path("upload/refs"),
    Path("runtime/cosyvoice"),
    Path("runtime/models"),
    Path("runtime/venv"),
    Path("evaluation"),
    Path("results/raw"),
)
PRIVATE_MARKER = ".voice-replication-private.json"
PRIVATE_MARKER_CONTENT = {
    "schema_version": 1,
    "purpose": "private voice workspace",
}


def _is_relative_to(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except _BuiltinValueError:
        return False
    return True


def resolve_private_root(
    repository_root: Path,
    explicit: Path | None,
    environment: Mapping[str, str],
) -> Path:
    """Return a canonical private root that is outside the repository."""
    raw = explicit
    if raw is None and environment.get("VOICE_KIT_PRIVATE_ROOT"):
        raw = Path(environment["VOICE_KIT_PRIVATE_ROOT"])
    if raw is None:
        raise ValueError("supply --private-root or VOICE_KIT_PRIVATE_ROOT")

    repository = repository_root.resolve(strict=True)
    candidate = raw.expanduser().resolve(strict=False)
    if _is_relative_to(candidate, repository):
        raise ValueError("private root must be outside the Git checkout")
    return candidate


def _marker_is_valid(marker: Path) -> bool:
    if not marker.is_file() or marker.is_symlink():
        return False
    try:
        content = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return content == PRIVATE_MARKER_CONTENT


def _validate_directory_targets(private_root: Path) -> None:
    for relative in PRIVATE_DIRECTORIES:
        target = private_root / relative
        resolved_target = target.resolve(strict=False)
        if not _is_relative_to(resolved_target, private_root):
            raise ValueError("private workspace directories must stay inside its root")
        for parent in (target, *target.parents):
            if parent == private_root.parent:
                break
            if (parent.exists() or parent.is_symlink()) and not parent.is_dir():
                raise ValueError(f"private workspace path is not a directory: {parent}")


def initialise_private_root(
    repository_root: Path, private_root: Path
) -> tuple[Path, ...]:
    """Create or repair the fixed layout of an authorised private root."""
    private = resolve_private_root(repository_root, private_root, {})
    marker = private / PRIVATE_MARKER

    if private.exists() and not private.is_dir():
        raise ValueError("private root must be a directory")

    if private.is_dir():
        entries = tuple(private.iterdir())
        if marker.exists() or marker.is_symlink():
            if not _marker_is_valid(marker):
                raise ValueError("private root does not contain a valid private workspace marker")
        elif entries:
            raise ValueError("refusing non-empty private root without a workspace marker")

    _validate_directory_targets(private)
    private.mkdir(parents=True, exist_ok=True)
    created = tuple(private / relative for relative in PRIVATE_DIRECTORIES)
    for directory in created:
        directory.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        marker.write_text(
            json.dumps(PRIVATE_MARKER_CONTENT, indent=2) + "\n",
            encoding="utf-8",
        )
    return created
