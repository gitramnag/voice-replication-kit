"""Expand listening matrices and contain private request I/O."""
from __future__ import annotations

import builtins
import hashlib
import itertools
import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from voice_replication_kit.errors import (
    ImmutableOutputError as FileExistsError,
    PrivateInputError as FileNotFoundError,
    UserValidationError as ValueError,
)


_BuiltinValueError = builtins.ValueError
_BuiltinFileExistsError = builtins.FileExistsError

from voice_replication_kit.requests import (
    MODEL_REVISION_PATTERN,
    REFERENCE_FILE_PATTERN,
    REFERENCE_SHA256_PATTERN,
    request_identity,
    validate_request,
)


REQUEST_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*__s\d+$")
SOURCE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
STYLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
EVALUATION_TEXT_SHAPES = {
    "short_clause",
    "connected_sentence",
    "two_sentences",
}
_PLAN_FIELDS = {
    "schema_version",
    "experiment_question",
    "prompts",
    "references",
    "seeds",
    "text_shapes",
}
_PROMPT_FIELDS = {
    "prompt_id",
    "source_segment_id",
    "unit_index",
    "style",
    "language",
    "text",
    "pronunciation_overrides",
}
_REFERENCE_FIELDS = {
    "reference_key",
    "reference_file",
    "reference_text",
    "reference_sha256",
}


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_exact_fields(
    value: Mapping[str, Any], expected: set[str], description: str
) -> None:
    missing = expected - set(value)
    unexpected = set(value) - expected
    if missing:
        raise ValueError(f"{description} is missing fields: {sorted(missing)}")
    if unexpected:
        raise ValueError(f"{description} has unexpected fields: {sorted(unexpected)}")


def validate_evaluation_plan(plan: Mapping[str, Any]) -> None:
    """Reject incomplete or ambiguous evaluation dimensions before expansion."""
    if not isinstance(plan, Mapping):
        raise ValueError("evaluation plan must be an object")
    _validate_exact_fields(plan, _PLAN_FIELDS, "evaluation plan")
    version = plan["schema_version"]
    if isinstance(version, bool) or version != 1:
        raise ValueError("evaluation plan schema_version must be 1")
    _non_empty_string(plan["experiment_question"], "experiment_question")

    for dimension in ("prompts", "references", "seeds", "text_shapes"):
        values = plan[dimension]
        if not _is_sequence(values) or not values:
            raise ValueError(f"evaluation plan {dimension} must be a non-empty array")

    prompt_ids: list[str] = []
    for index, prompt in enumerate(plan["prompts"], 1):
        if not isinstance(prompt, Mapping):
            raise ValueError(f"prompt {index} must be an object")
        _validate_exact_fields(prompt, _PROMPT_FIELDS, f"prompt {index}")
        prompt_id = _non_empty_string(prompt["prompt_id"], "prompt_id")
        if not SOURCE_KEY_PATTERN.fullmatch(prompt_id):
            raise ValueError("prompt_id must use lowercase letters, digits, _ or -")
        prompt_ids.append(prompt_id)
        _non_empty_string(prompt["source_segment_id"], "source_segment_id")
        unit_index = prompt["unit_index"]
        if isinstance(unit_index, bool) or not isinstance(unit_index, int) or unit_index < 1:
            raise ValueError("unit_index must be a positive integer")
        style = _non_empty_string(prompt["style"], "style")
        if not STYLE_PATTERN.fullmatch(style):
            raise ValueError("style must use lowercase letters, digits, and underscores")
        language = _non_empty_string(prompt["language"], "language")
        if len(language) < 2:
            raise ValueError("language must contain at least two characters")
        text = _non_empty_string(prompt["text"], "text")
        if len(text) > 220:
            raise ValueError("text must contain at most 220 characters")
        overrides = prompt["pronunciation_overrides"]
        if not isinstance(overrides, Mapping) or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            or not value
            for key, value in overrides.items()
        ):
            raise ValueError("pronunciation_overrides must contain non-empty strings")
    if len(set(prompt_ids)) != len(prompt_ids):
        raise ValueError("prompt_id values must be unique")

    reference_keys: list[str] = []
    for index, reference in enumerate(plan["references"], 1):
        if not isinstance(reference, Mapping):
            raise ValueError(f"reference {index} must be an object")
        _validate_exact_fields(reference, _REFERENCE_FIELDS, f"reference {index}")
        reference_key = _non_empty_string(reference["reference_key"], "reference_key")
        if not SOURCE_KEY_PATTERN.fullmatch(reference_key):
            raise ValueError("reference_key must use lowercase letters, digits, _ or -")
        reference_keys.append(reference_key)
        reference_file = str(reference["reference_file"])
        if not REFERENCE_FILE_PATTERN.fullmatch(reference_file):
            raise ValueError("reference_file must name one .wav beneath refs/")
        _non_empty_string(reference["reference_text"], "reference_text")
        if not REFERENCE_SHA256_PATTERN.fullmatch(str(reference["reference_sha256"])):
            raise ValueError("reference_sha256 must be a lowercase SHA-256 digest")
    if len(set(reference_keys)) != len(reference_keys):
        raise ValueError("reference_key values must be unique")

    seeds = plan["seeds"]
    if any(
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or seed < 0
        or seed > 2**32 - 1
        for seed in seeds
    ):
        raise ValueError("seeds must be 32-bit unsigned integers")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")

    text_shapes = plan["text_shapes"]
    if any(shape not in EVALUATION_TEXT_SHAPES for shape in text_shapes):
        raise ValueError("text_shapes contains an unsupported text shape")
    if len(set(text_shapes)) != len(text_shapes):
        raise ValueError("text_shapes must be unique")


def _materialise_evaluation_row(
    prompt: Mapping[str, Any],
    reference: Mapping[str, Any],
    seed: int,
    text_shape: str,
    model_revision: str,
) -> dict[str, Any]:
    reference_text = str(reference["reference_text"])
    row = {
        "schema_version": 1,
        "prompt_id": str(prompt["prompt_id"]),
        "source_segment_id": str(prompt["source_segment_id"]),
        "unit_index": int(prompt["unit_index"]),
        "style": str(prompt["style"]),
        "language": str(prompt["language"]),
        "text": str(prompt["text"]),
        "seed": int(seed),
        "reference_key": str(reference["reference_key"]),
        "reference_file": str(reference["reference_file"]),
        "reference_text": reference_text,
        "reference_sha256": str(reference["reference_sha256"]),
        "reference_text_sha256": hashlib.sha256(
            reference_text.encode("utf-8")
        ).hexdigest(),
        "text_shape": str(text_shape),
        "model_revision": model_revision,
        "pronunciation_overrides": dict(prompt["pronunciation_overrides"]),
    }
    row["request_id"] = request_identity(row)
    return row


def build_evaluation_matrix(
    plan: Mapping[str, Any], model_revision: str
) -> list[dict[str, Any]]:
    """Expand every prompt, reference, seed, and text-shape combination."""
    validate_evaluation_plan(plan)
    if not MODEL_REVISION_PATTERN.fullmatch(str(model_revision)):
        raise ValueError("model_revision must be an exact lowercase commit")
    rows = [
        _materialise_evaluation_row(prompt, reference, seed, shape, model_revision)
        for prompt, reference, seed, shape in itertools.product(
            plan["prompts"],
            plan["references"],
            plan["seeds"],
            plan["text_shapes"],
        )
    ]
    for row in rows:
        validate_request(row)
    rows.sort(key=lambda row: row["request_id"])
    request_ids = [row["request_id"] for row in rows]
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("request ids must be unique")
    return rows


def expand_candidates(
    requests: Sequence[Mapping[str, Any]], seeds: Iterable[int]
) -> list[dict[str, Any]]:
    """Expand each request into a primary-first, de-duplicated seed matrix."""
    candidates: list[dict[str, Any]] = []
    alternates = [int(seed) for seed in seeds]
    for request in requests:
        primary_id = str(request["request_id"])
        match = re.fullmatch(r"(.+)__s\d+", primary_id)
        if not match:
            raise ValueError(f"request id lacks a seed suffix: {primary_id}")
        primary_seed = int(request["seed"])
        ordered: list[int] = []
        for seed in [primary_seed, *alternates]:
            if seed < 0 or seed > 2**32 - 1:
                raise ValueError("candidate seeds must be 32-bit unsigned integers")
            if seed not in ordered:
                ordered.append(seed)
        for index, seed in enumerate(ordered, 1):
            candidate = dict(request)
            candidate.update(
                {
                    "seed": seed,
                    "candidate_of": primary_id,
                    "candidate_index": index,
                    "selection_required": True,
                }
            )
            candidate["request_id"] = request_identity(candidate)
            candidates.append(candidate)
    return candidates


def _reference_relative(request: Mapping[str, Any]) -> PurePosixPath:
    value = str(request.get("reference_file", ""))
    if not REFERENCE_FILE_PATTERN.fullmatch(value):
        raise ValueError("reference must stay beneath private/upload/refs")
    path = PurePosixPath(value)
    return path


def resolve_reference_path(
    root: Path, request: Mapping[str, Any], require_exists: bool = True
) -> Path:
    """Resolve only one file directly beneath ``<private-root>/upload/refs``."""
    root = Path(root).resolve()
    upload = (root / "upload").resolve()
    refs = (upload / "refs").resolve()
    reference = (upload / Path(*_reference_relative(request).parts)).resolve()
    try:
        reference.relative_to(refs)
    except _BuiltinValueError as exc:
        raise ValueError("reference must stay beneath private/upload/refs") from exc
    if reference.parent != refs:
        raise ValueError("reference must stay beneath private/upload/refs")
    if require_exists and not reference.is_file():
        raise FileNotFoundError(f"private reference does not exist: {reference.name}")
    return reference


def next_output_path(root: Path, request_id: str) -> Path:
    """Choose a private filename that cannot overwrite an earlier render."""
    if not REQUEST_ID_PATTERN.fullmatch(str(request_id)):
        raise ValueError("request_id is unsafe for an output filename")
    directory = Path(root).resolve() / "results" / "raw" / "cosyvoice3"
    candidate = directory / f"{request_id}.wav"
    retry = 2
    while candidate.exists():
        candidate = directory / f"{request_id}__r{retry}.wav"
        retry += 1
    return candidate


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    ).encode("utf-8")


def write_jsonl_immutable(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Write once, permit an identical retry, and reject changed content."""
    path = Path(path)
    payload = _jsonl_bytes(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except _BuiltinFileExistsError:
            if path.read_bytes() != payload:
                raise FileExistsError(
                    f"refusing to replace existing request pack: {path}"
                ) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_requests(path: Path) -> list[dict[str, Any]]:
    """Load and validate a private JSONL request pack."""
    rows: list[dict[str, Any]] = []
    try:
        lines = Path(path).read_text("utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise FileNotFoundError("cannot read private request pack") from error
    for line_number, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(f"request line {line_number} is invalid") from error
        if not isinstance(row, dict):
            raise ValueError(f"request line {line_number} must be an object")
        try:
            validate_request(row)
        except _BuiltinValueError as exc:
            raise ValueError(f"request line {line_number}: {exc}") from exc
        rows.append(row)
    if not rows:
        raise ValueError("request pack is empty")
    request_ids = [str(row["request_id"]) for row in rows]
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("request ids must be unique")
    return rows


def sha256_file(path: Path) -> str:
    """Hash a private file without loading it all into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
