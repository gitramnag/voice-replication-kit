"""Command-line entry point for the voice replication workflow."""

import argparse
import builtins
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from voice_replication_kit.matrix import (
    build_evaluation_matrix,
    resolve_reference_path,
    sha256_file,
    write_jsonl_immutable,
)
from voice_replication_kit.errors import UserValidationError as ValueError
from voice_replication_kit.private_root import (
    initialise_private_root,
    resolve_private_root,
)
from voice_replication_kit.privacy import run_audit
from voice_replication_kit.requests import build_requests, validate_private_profile
from voice_replication_kit.scoring import build_blind_pack


_BuiltinValueError = builtins.ValueError


def _trusted_source_root(package_directory: Path, error_message: str) -> Path:
    if (
        package_directory.name != "voice_replication_kit"
        or package_directory.parent.name != "src"
    ):
        raise RuntimeError(error_message)
    source_root = package_directory.parent.parent
    markers = (
        source_root / "pyproject.toml",
        source_root / "configs" / "pins.json",
        source_root / "configs" / "model-manifest.json",
        source_root / "configs" / "runtime-lock.txt",
    )
    try:
        project = markers[0].read_text(encoding="utf-8")
        pins = json.loads(markers[1].read_text(encoding="utf-8"))
        json.loads(markers[2].read_text(encoding="utf-8"))
        lock = markers[3].read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(error_message) from error
    if (
        'name = "voice-replication-kit"' not in project
        or not isinstance(pins, dict)
        or pins.get("schema_version") != 1
        or "--hash=sha256:" not in lock
    ):
        raise RuntimeError(error_message)
    return source_root.resolve(strict=True)


def _marker_publication_root(source_root: Path) -> Path:
    for candidate in (source_root, *source_root.parents):
        marker = candidate / ".git"
        if marker.exists() or marker.is_symlink():
            return candidate.resolve(strict=True)
    return source_root


def _discover_repository_roots(
    package_file: Path = Path(__file__),
) -> tuple[Path, Path]:
    """Return the kit resource root and its enclosing publication boundary."""
    error_message = "cannot locate a trusted voice-kit source root"
    try:
        package_directory = package_file.resolve(strict=True).parent
    except OSError as error:
        raise RuntimeError(error_message) from error
    resource_root = _trusted_source_root(package_directory, error_message)
    result: subprocess.CompletedProcess[str] | None
    try:
        result = subprocess.run(
            ["git", "-C", str(package_directory), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        try:
            publication_root = Path(result.stdout.strip()).resolve(strict=True)
            package_directory.relative_to(publication_root)
        except OSError as error:
            raise RuntimeError(error_message) from error
        except _BuiltinValueError as error:
            raise RuntimeError(error_message) from error
        return resource_root, publication_root
    return resource_root, _marker_publication_root(resource_root)


def _discover_repository_root(package_file: Path = Path(__file__)) -> Path:
    """Return the trusted root containing this kit's public resources."""
    return _discover_repository_roots(package_file)[0]


def _initialise_private(args: argparse.Namespace) -> int:
    _resource_root, publication_root = _discover_repository_roots()
    private_root = resolve_private_root(publication_root, args.private_root, os.environ)
    initialise_private_root(publication_root, private_root)
    return 0


def _resolve_command_root(args: argparse.Namespace) -> tuple[Path, Path]:
    resource_root, publication_root = _discover_repository_roots()
    private_root = resolve_private_root(publication_root, args.private_root, os.environ)
    return resource_root, private_root


def _private_path(
    private_root: Path,
    supplied: Path | None,
    default: Path,
    *,
    beneath: Path | None = None,
) -> Path:
    candidate = default if supplied is None else supplied.expanduser().resolve(strict=False)
    candidate = candidate.resolve(strict=False)
    boundary = (private_root if beneath is None else beneath).resolve(strict=False)
    try:
        candidate.relative_to(boundary)
    except _BuiltinValueError as error:
        raise ValueError("private paths must resolve beneath the private root") from error
    return candidate


def _load_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {description}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def _validate_profile_references(private_root: Path, profile: Mapping[str, Any]) -> None:
    recipes = profile["recipes"]
    for style, recipe in recipes.items():
        reference = resolve_reference_path(private_root, recipe)
        if sha256_file(reference) != recipe["reference_sha256"]:
            raise ValueError(f"private reference hash changed for recipe {style}")


def _profile_path(private_root: Path, supplied: Path | None) -> Path:
    return _private_path(
        private_root,
        supplied,
        private_root / "upload" / "private-profile.json",
    )


def _validate_profile_command(args: argparse.Namespace) -> int:
    _repository_root, private_root = _resolve_command_root(args)
    profile = _load_json_object(
        _profile_path(private_root, args.profile), "private profile"
    )
    validate_private_profile(profile)
    _validate_profile_references(private_root, profile)
    recipe_count = len(profile["recipes"])
    noun = "recipe" if recipe_count == 1 else "recipes"
    print(f"validated {recipe_count} private profile {noun}")
    return 0


def _reviewed_model_revision(repository_root: Path) -> str:
    pins = _load_json_object(repository_root / "configs" / "pins.json", "pins")
    model = pins.get("model")
    if not isinstance(model, Mapping):
        raise ValueError("pins must contain a model object")
    revision = str(model.get("revision", ""))
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise ValueError("reviewed model revision must be an exact lowercase commit")
    return revision


def _build_requests_command(args: argparse.Namespace) -> int:
    repository_root, private_root = _resolve_command_root(args)
    upload = private_root / "upload"
    document_path = _private_path(
        private_root,
        args.document,
        upload / "production-script.json",
    )
    profile_path = _profile_path(private_root, args.profile)
    output_path = _private_path(
        private_root,
        args.output,
        upload / "requests.jsonl",
        beneath=upload,
    )
    document = _load_json_object(document_path, "production document")
    profile = _load_json_object(profile_path, "private profile")
    validate_private_profile(profile)
    _validate_profile_references(private_root, profile)
    rows = build_requests(
        document,
        profile,
        _reviewed_model_revision(repository_root),
    )
    write_jsonl_immutable(output_path, rows)
    print(f"wrote {len(rows)} immutable requests to {output_path}")
    return 0


def _validate_evaluation_references(
    private_root: Path, plan: Mapping[str, Any]
) -> None:
    references = plan.get("references")
    if not isinstance(references, Sequence) or isinstance(references, (str, bytes)):
        return
    for reference in references:
        if not isinstance(reference, Mapping):
            continue
        path = resolve_reference_path(private_root, reference)
        if sha256_file(path) != reference.get("reference_sha256"):
            raise ValueError("private reference hash changed for evaluation reference")


def _build_matrix_command(args: argparse.Namespace) -> int:
    repository_root, private_root = _resolve_command_root(args)
    plan_path = _private_path(
        private_root,
        args.plan,
        private_root / "upload" / "evaluation-plan.json",
    )
    output_path = _private_path(
        private_root,
        args.output,
        private_root / "evaluation" / "matrix.jsonl",
    )
    plan = _load_json_object(plan_path, "evaluation plan")
    _validate_evaluation_references(private_root, plan)
    rows = build_evaluation_matrix(
        plan,
        _reviewed_model_revision(repository_root),
    )
    write_jsonl_immutable(output_path, rows)
    print(f"wrote {len(rows)} immutable evaluation candidates")
    return 0


def _load_jsonl_objects(path: Path, description: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"cannot read {description}") from error
    for line_number, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(f"{description} line {line_number} is invalid") from error
        if not isinstance(value, dict):
            raise ValueError(f"{description} line {line_number} must be an object")
        rows.append(value)
    if not rows:
        raise ValueError(f"{description} is empty")
    return rows


def _build_blind_map_command(args: argparse.Namespace) -> int:
    _repository_root, private_root = _resolve_command_root(args)
    matrix_path = _private_path(
        private_root,
        args.matrix,
        private_root / "evaluation" / "matrix.jsonl",
    )
    output_path = _private_path(
        private_root,
        args.output,
        private_root / "evaluation" / "blind-candidates.jsonl",
    )
    secret_path = _private_path(
        private_root,
        args.secret_output,
        private_root / "evaluation" / "unblinding-map.json",
    )
    rows = _load_jsonl_objects(matrix_path, "evaluation matrix")
    visible, secret = build_blind_pack(rows)
    write_jsonl_immutable(output_path, visible)
    write_jsonl_immutable(secret_path, [secret])
    print(f"wrote {len(visible)} immutable blind candidates and one private map")
    return 0


def _audit_command(args: argparse.Namespace) -> int:
    return run_audit(args.root, args.mode, args.private_terms_file)


def _render_command(
    args: argparse.Namespace,
    *,
    repository_root: Path | None = None,
    publication_root: Path | None = None,
) -> int:
    from voice_replication_kit.rendering import (
        CosyVoiceBackend,
        RenderOptions,
        render_requests,
    )

    if repository_root is None:
        discovered, boundary = _discover_repository_roots()
    else:
        discovered = repository_root
        boundary = repository_root if publication_root is None else publication_root
    private_root = resolve_private_root(boundary, args.private_root, os.environ)
    request_pack = _private_path(
        private_root,
        args.requests,
        private_root / "upload" / "requests.jsonl",
    )
    profile = None
    if args.profile is not None:
        profile = _private_path(
            private_root,
            args.profile,
            private_root / "upload" / "private-profile.json",
        )
    options = RenderOptions(
        smoke=args.smoke,
        accept_smoke=args.accept_smoke,
        validate_only=args.validate_only,
        request_id=args.request_id,
        max_batch_seconds=args.max_batch_seconds,
        profile=profile,
    )
    backend = CosyVoiceBackend(
        discovered, precision=args.precision, publication_root=boundary
    )
    summary = render_requests(private_root, request_pack, options, backend)
    if args.validate_only:
        print(f"validated {summary.validated} private CosyVoice requests")
    else:
        print(
            f"rendered {summary.rendered}; failed {summary.failed}; "
            f"stopped {summary.stopped}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voice-kit",
        description="Build and reuse an authorised private voice with CosyVoice 3.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init_private = commands.add_parser("init-private")
    init_private.add_argument("--private-root", type=Path)
    init_private.set_defaults(handler=_initialise_private)
    validate_profile = commands.add_parser("validate-profile")
    validate_profile.add_argument("--private-root", type=Path)
    validate_profile.add_argument("--profile", type=Path)
    validate_profile.set_defaults(handler=_validate_profile_command)
    request_builder = commands.add_parser("build-requests")
    request_builder.add_argument("--private-root", type=Path)
    request_builder.add_argument("--document", type=Path)
    request_builder.add_argument("--profile", type=Path)
    request_builder.add_argument("--output", type=Path)
    request_builder.set_defaults(handler=_build_requests_command)
    matrix_builder = commands.add_parser("build-matrix")
    matrix_builder.add_argument("--private-root", type=Path)
    matrix_builder.add_argument("--plan", type=Path)
    matrix_builder.add_argument("--output", type=Path)
    matrix_builder.set_defaults(handler=_build_matrix_command)
    blind_map_builder = commands.add_parser("build-blind-map")
    blind_map_builder.add_argument("--private-root", type=Path)
    blind_map_builder.add_argument("--matrix", type=Path)
    blind_map_builder.add_argument("--output", type=Path)
    blind_map_builder.add_argument("--secret-output", type=Path)
    blind_map_builder.set_defaults(handler=_build_blind_map_command)
    render = commands.add_parser("render")
    render.add_argument("--private-root", type=Path)
    render.add_argument("--requests", type=Path)
    render.add_argument("--profile", type=Path)
    render.add_argument("--request-id")
    render.add_argument("--smoke", action="store_true")
    render.add_argument("--accept-smoke")
    render.add_argument("--validate-only", action="store_true")
    render.add_argument("--max-batch-seconds", type=float, default=8 * 60 * 60)
    render.add_argument("--precision", choices=("fp16", "fp32"), default="fp16")
    render.set_defaults(handler=_render_command)
    audit = commands.add_parser("audit")
    audit.add_argument("--root", type=Path, default=Path.cwd())
    audit.add_argument(
        "--mode", choices=("tree", "staged", "history"), default="tree"
    )
    audit.add_argument("--private-terms-file", type=Path)
    audit.set_defaults(handler=_audit_command)
    return parser


def _dispatch(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


def _safe_validation_message(
    argv: Sequence[str] | None, error: ValueError
) -> str:
    arguments = list(sys.argv[1:] if argv is None else argv)
    command = next((item for item in arguments if not item.startswith("-")), "")
    input_type = {
        "init-private": "private root",
        "validate-profile": "private profile",
        "build-requests": "production inputs",
        "build-matrix": "evaluation plan",
        "build-blind-map": "evaluation matrix",
        "render": "render inputs",
        "audit": "publication audit",
    }.get(command, "input")
    text = str(error).casefold()
    if "reference hash changed" in text:
        reason = "reference hash changed"
    elif "cannot read" in text:
        reason = "file is missing or malformed"
    elif "must be a json object" in text:
        reason = "JSON object is required"
    elif "must resolve beneath" in text or "must be outside" in text:
        reason = "path is outside the approved private root"
    elif "refusing to replace" in text or "already exists" in text:
        reason = "output already exists"
    elif "does not exist" in text:
        reason = "required file is missing"
    else:
        reason = "input validation failed"
    return f"voice-kit: {input_type}: {reason}"


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return _dispatch(argv)
    except ValueError as error:
        print(_safe_validation_message(argv, error), file=sys.stderr)
        return 1
