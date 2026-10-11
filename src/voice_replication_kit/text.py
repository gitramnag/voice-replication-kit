"""Prepare written copy for predictable speech rendering."""
from __future__ import annotations

import re
from collections.abc import Mapping

from voice_replication_kit.errors import UserValidationError as ValueError


MAX_CHUNK_CHARACTERS = 220


def apply_pronunciation_overrides(
    text: str, overrides: Mapping[str, str] | None
) -> str:
    """Apply caller-supplied whole-word substitutions in insertion order."""
    output = str(text)
    for written, spoken in (overrides or {}).items():
        if not str(written).strip() or not str(spoken).strip():
            raise ValueError(
                "pronunciation overrides require non-empty written and spoken forms"
            )
        output = re.sub(
            rf"\b{re.escape(str(written))}\b",
            str(spoken),
            output,
            flags=re.IGNORECASE,
        )
    return output


def _wrap_words(text: str, limit: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        if len(word) > limit:
            raise ValueError(
                f"one token is longer than the {limit}-character speech limit"
            )
        candidate = word if not current else f"{current} {word}"
        if current and len(candidate) > limit:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def speech_sentences(text: str, max_characters: int = MAX_CHUNK_CHARACTERS) -> list[str]:
    """Return sentence-like units, splitting oversized sentences at word boundaries."""
    if max_characters < 20:
        raise ValueError("max_characters must be at least 20")
    normalized = re.sub(r"\s+", " ", str(text)).strip()
    if not normalized:
        return []
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", normalized)
        if part.strip()
    ]
    return [
        chunk
        for sentence in sentences
        for chunk in _wrap_words(sentence, max_characters)
    ]


def prepare_for_speech(
    text: str,
    overrides: Mapping[str, str] | None = None,
    max_characters: int = MAX_CHUNK_CHARACTERS,
) -> list[str]:
    """Return pronunciation-adjusted chunks no longer than *max_characters*."""
    units = speech_sentences(
        apply_pronunciation_overrides(text, overrides),
        max_characters=max_characters,
    )
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current} {unit}"
        if current and len(candidate) > max_characters:
            chunks.append(current)
            current = unit
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
