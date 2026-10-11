"""Validate private recipes and build deterministic CosyVoice request rows."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from voice_replication_kit.errors import UserValidationError as ValueError

from voice_replication_kit.text import (
    MAX_CHUNK_CHARACTERS,
    apply_pronunciation_overrides,
    speech_sentences,
)


TEXT_SHAPES = {"short_clause", "connected_sentence", "two_sentences"}
REFERENCE_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REFERENCE_FILE_PATTERN = re.compile(
    r"^refs/[A-Za-z0-9][A-Za-z0-9._-]*\.wav$"
)
MODEL_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
IDENTITY_FIELDS = (
    "source_segment_id",
    "unit_index",
    "text",
    "style",
    "reference_sha256",
    "reference_text_sha256",
    "seed",
    "text_shape",
    "model_revision",
)
STYLE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"serious|authorit|risk|warning|caution|critical|security", "serious_authoritative"),
    (r"energetic|excite|reveal|highlight|breakthrough|best part", "excited_energetic"),
    (r"warm|friendly|welcome|intro|outro|thank|invite", "warm_friendly"),
    (r"curious|question|inquiry", "curious_questioning"),
    (r"empathetic|calm|reassur|support", "empathetic_calm"),
    (r"neutral|explain|inform|walk.?through|instruction|narrat", "narration_neutral"),
)

REQUIRED_REQUEST_FIELDS = {
    "schema_version",
    "request_id",
    "prompt_id",
    "source_segment_id",
    "unit_index",
    "style",
    "language",
    "text",
    "seed",
    "reference_file",
    "reference_text",
    "reference_sha256",
    "reference_text_sha256",
    "text_shape",
    "model_revision",
    "pronunciation_overrides",
}
CANDIDATE_REQUEST_FIELDS = {"candidate_of", "candidate_index", "selection_required"}
EVALUATION_REQUEST_FIELDS = {"reference_key"}
OPTIONAL_REQUEST_FIELDS = CANDIDATE_REQUEST_FIELDS | EVALUATION_REQUEST_FIELDS


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_reference_file(value: Any) -> str:
    reference = str(value)
    if not REFERENCE_FILE_PATTERN.fullmatch(reference):
        raise ValueError(
            "reference_file must name one restricted lowercase .wav beneath refs/"
        )
    return reference


def validate_private_profile(profile: Mapping[str, Any]) -> None:
    """Reject incomplete or unsafe speaker recipes before request generation."""
    unexpected = set(profile) - {"schema_version", "model", "recipes"}
    if unexpected:
        raise ValueError(f"private profile has unexpected fields: {sorted(unexpected)}")
    if (
        not _is_int(profile.get("schema_version"))
        or profile.get("schema_version") != 1
        or profile.get("model") != "cosyvoice3"
    ):
        raise ValueError("private profile must use schema_version 1 and model cosyvoice3")
    recipes = profile.get("recipes")
    if not isinstance(recipes, Mapping) or not recipes:
        raise ValueError("private profile needs a non-empty recipes object")
    if "narration_neutral" not in recipes:
        raise ValueError("private profile needs a narration_neutral fallback recipe")
    for style, raw_recipe in recipes.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(style)):
            raise ValueError(f"invalid style key: {style!r}")
        if not isinstance(raw_recipe, Mapping):
            raise ValueError(f"recipe {style} must be an object")
        recipe = raw_recipe
        unexpected_recipe = set(recipe) - {
            "reference_file",
            "reference_text",
            "reference_sha256",
            "seed",
            "text_shape",
        }
        if unexpected_recipe:
            raise ValueError(
                f"recipe {style} has unexpected fields: {sorted(unexpected_recipe)}"
            )
        _validate_reference_file(recipe.get("reference_file", ""))
        if not str(recipe.get("reference_text", "")).strip():
            raise ValueError(f"recipe {style} needs a private reference_text")
        if not REFERENCE_SHA256_PATTERN.fullmatch(
            str(recipe.get("reference_sha256", ""))
        ):
            raise ValueError(f"recipe {style} needs a lowercase SHA-256 reference hash")
        if not _is_int(recipe.get("seed")) or not 0 <= int(recipe["seed"]) <= 2**32 - 1:
            raise ValueError(f"recipe {style} seed must be a 32-bit unsigned integer")
        if recipe.get("text_shape") not in TEXT_SHAPES:
            raise ValueError(f"recipe {style} has an unsupported text_shape")


def validate_document(document: Mapping[str, Any]) -> None:
    """Validate the speaker-agnostic script document consumed by the builder."""
    unexpected = set(document) - {"schema_version", "title", "language", "segments"}
    if unexpected:
        raise ValueError(f"document has unexpected fields: {sorted(unexpected)}")
    if not _is_int(document.get("schema_version")) or document.get("schema_version") != 1:
        raise ValueError("document schema_version must be 1")
    if not str(document.get("language", "")).strip():
        raise ValueError("document needs a language")
    segments = document.get("segments")
    if not isinstance(segments, Sequence) or isinstance(segments, (str, bytes)) or not segments:
        raise ValueError("document needs a non-empty segments list")
    seen: set[str] = set()
    for segment in segments:
        if not isinstance(segment, Mapping):
            raise ValueError("every segment must be an object")
        unexpected_segment = set(segment) - {
            "id",
            "intent",
            "style",
            "text",
            "pronunciation_overrides",
        }
        if unexpected_segment:
            raise ValueError(
                f"segment has unexpected fields: {sorted(unexpected_segment)}"
            )
        segment_id = str(segment.get("id", "")).strip()
        if not segment_id or segment_id in seen:
            raise ValueError("every segment needs a unique non-empty id")
        seen.add(segment_id)
        if not str(segment.get("text", "")).strip():
            raise ValueError(f"segment {segment_id} needs speakable text")
        overrides = segment.get("pronunciation_overrides", {})
        if not isinstance(overrides, Mapping):
            raise ValueError(f"segment {segment_id} pronunciation_overrides must be an object")
        apply_pronunciation_overrides(str(segment["text"]), overrides)


def route_style(segment: Mapping[str, Any], recipes: Mapping[str, Any]) -> str:
    """Use an explicit style first, then generic intent routing, then neutral."""
    explicit = str(segment.get("style", "")).strip()
    if explicit:
        if explicit not in recipes:
            raise ValueError(f"unknown production style: {explicit}")
        return explicit
    intent = str(segment.get("intent", "")).lower()
    for pattern, style in STYLE_PATTERNS:
        if style in recipes and re.search(pattern, intent):
            return style
    return "narration_neutral"


def _shape_units(text: str, shape: str) -> list[str]:
    sentences = speech_sentences(text, max_characters=MAX_CHUNK_CHARACTERS)
    if shape == "short_clause":
        return [
            clause.strip()
            for sentence in sentences
            for clause in re.split(r"(?<=[,;:])\s+", sentence)
            if clause.strip()
        ]
    if shape == "connected_sentence":
        return sentences
    if shape == "two_sentences":
        units: list[str] = []
        index = 0
        while index < len(sentences):
            current = sentences[index]
            if index + 1 < len(sentences):
                pair = f"{current} {sentences[index + 1]}"
                if len(pair) <= MAX_CHUNK_CHARACTERS:
                    current = pair
                    index += 1
            units.append(current)
            index += 1
        return units
    raise ValueError(f"unsupported text shape: {shape}")


def slug(value: object) -> str:
    """Convert a source segment identifier into a safe filename component."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return cleaned or "segment"


def request_identity(row: Mapping[str, Any]) -> str:
    """Bind a stable request identifier to every render-changing input."""
    payload = {key: row[key] for key in IDENTITY_FIELDS}
    if "reference_text" in row:
        actual_text_digest = hashlib.sha256(
            str(row["reference_text"]).encode("utf-8")
        ).hexdigest()
        if actual_text_digest != payload["reference_text_sha256"]:
            payload["reference_text_sha256"] = (
                f"{payload['reference_text_sha256']}:{actual_text_digest}"
            )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:16]
    return (
        f"{slug(row['source_segment_id'])}_u{int(row['unit_index']):02d}_"
        f"{digest}__s{int(row['seed'])}"
    )


def build_requests(
    document: Mapping[str, Any],
    private_profile: Mapping[str, Any],
    model_revision: str,
) -> list[dict[str, Any]]:
    """Build stable private request rows from a public script and local profile."""
    validate_document(document)
    validate_private_profile(private_profile)
    if not MODEL_REVISION_PATTERN.fullmatch(str(model_revision)):
        raise ValueError("model_revision must be an exact lowercase 40-character commit")
    recipes = private_profile["recipes"]
    rows: list[dict[str, Any]] = []
    for segment in document["segments"]:
        segment_id = str(segment["id"]).strip()
        style = route_style(segment, recipes)
        recipe = recipes[style]
        overrides = dict(segment.get("pronunciation_overrides") or {})
        prepared = apply_pronunciation_overrides(str(segment["text"]), overrides)
        units = _shape_units(prepared, str(recipe["text_shape"]))
        if not units:
            raise ValueError(f"segment {segment_id} contains no speakable text")
        seed = int(recipe["seed"])
        reference_text = str(recipe["reference_text"])
        reference_text_sha256 = hashlib.sha256(
            reference_text.encode("utf-8")
        ).hexdigest()
        for unit_index, text in enumerate(units, 1):
            row = {
                "schema_version": 1,
                "source_segment_id": segment_id,
                "unit_index": unit_index,
                "style": style,
                "language": str(document["language"]),
                "text": text,
                "seed": seed,
                "reference_file": _validate_reference_file(recipe["reference_file"]),
                "reference_text": reference_text,
                "reference_sha256": str(recipe["reference_sha256"]),
                "reference_text_sha256": reference_text_sha256,
                "text_shape": str(recipe["text_shape"]),
                "model_revision": str(model_revision),
                "pronunciation_overrides": overrides,
            }
            request_id = request_identity(row)
            row["request_id"] = request_id
            row["prompt_id"] = f"production_{request_id.rsplit('__s', 1)[0]}"
            rows.append(row)
    return rows


def validate_request(row: Mapping[str, Any]) -> None:
    """Validate one fully materialized private request row."""
    missing = REQUIRED_REQUEST_FIELDS - row.keys()
    if missing:
        raise ValueError(f"request is missing fields: {sorted(missing)}")
    unexpected = set(row) - REQUIRED_REQUEST_FIELDS - OPTIONAL_REQUEST_FIELDS
    if unexpected:
        raise ValueError(f"request has unexpected fields: {sorted(unexpected)}")
    if not _is_int(row.get("schema_version")) or row.get("schema_version") != 1:
        raise ValueError("request schema_version must be 1")
    request_match = re.fullmatch(
        r"[a-z0-9][a-z0-9_-]*__s(?P<seed>\d+)", str(row["request_id"])
    )
    if not request_match:
        raise ValueError("request_id is unsafe")
    if not _is_int(row.get("seed")) or not 0 <= int(row["seed"]) <= 2**32 - 1:
        raise ValueError("request seed must be a 32-bit unsigned integer")
    if int(request_match.group("seed")) != int(row["seed"]):
        raise ValueError("request_id seed suffix does not match seed")
    if not _is_int(row.get("unit_index")) or int(row["unit_index"]) < 1:
        raise ValueError("request unit_index must be a positive integer")
    for field in ("prompt_id", "source_segment_id"):
        if not str(row.get(field, "")).strip():
            raise ValueError(f"request {field} is empty")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", str(row.get("style", ""))):
        raise ValueError("request style is invalid")
    if len(str(row.get("language", "")).strip()) < 2:
        raise ValueError("request language is invalid")
    text = str(row.get("text", "")).strip()
    if not text:
        raise ValueError("request text is empty")
    if len(text) > MAX_CHUNK_CHARACTERS:
        raise ValueError(f"request text exceeds {MAX_CHUNK_CHARACTERS} characters")
    _validate_reference_file(row["reference_file"])
    if not str(row.get("reference_text", "")).strip():
        raise ValueError("request reference_text is empty")
    if not REFERENCE_SHA256_PATTERN.fullmatch(str(row.get("reference_sha256", ""))):
        raise ValueError("request reference_sha256 is invalid")
    expected_text_digest = hashlib.sha256(
        str(row["reference_text"]).encode("utf-8")
    ).hexdigest()
    if row.get("reference_text_sha256") != expected_text_digest:
        raise ValueError("request reference_text_sha256 does not match reference_text")
    if not MODEL_REVISION_PATTERN.fullmatch(str(row.get("model_revision", ""))):
        raise ValueError("request model_revision is invalid")
    if row.get("text_shape") not in TEXT_SHAPES:
        raise ValueError("request text_shape is unsupported")
    overrides = row.get("pronunciation_overrides")
    if not isinstance(overrides, Mapping):
        raise ValueError("request pronunciation_overrides must be an object")
    apply_pronunciation_overrides("validation text", overrides)
    if "reference_key" in row:
        reference_key = row["reference_key"]
        if not isinstance(reference_key, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9_-]*", reference_key
        ):
            raise ValueError("request reference_key is invalid")
    if row["request_id"] != request_identity(row):
        raise ValueError("request_id does not match the render inputs")

    candidate_fields = CANDIDATE_REQUEST_FIELDS & row.keys()
    if candidate_fields and candidate_fields != CANDIDATE_REQUEST_FIELDS:
        raise ValueError("candidate request fields must be supplied together")
    if candidate_fields:
        if not str(row["candidate_of"]).strip():
            raise ValueError("candidate_of is empty")
        if not _is_int(row["candidate_index"]) or int(row["candidate_index"]) < 1:
            raise ValueError("candidate_index must be a positive integer")
        if not isinstance(row["selection_required"], bool):
            raise ValueError("selection_required must be a boolean")
