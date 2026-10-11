"""Load, validate, and render the public speaker-agnostic recording corpus."""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


SPECIAL_STYLES = {"calibration", "mixed", "paralinguistic"}
PRIVATE_IDENTITY_PATTERN = re.compile(
    r"(?i)<(?:speaker|evaluator)-name>|(?:speaker|evaluator)[ _-]?id"
)
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:\\Users\\"),
    re.compile(r"(?i)(?<![\w.-])/" "home" r"/[^/\s]+/"),
    re.compile(r"(?i)(?<![\w.-])/" "Users" r"/[^/\s]+/"),
)


@dataclass(frozen=True)
class Prompt:
    id: str
    block: str
    block_label: str
    tier: int
    style: str
    target_sec: float
    text: str
    note: str
    source: str | None
    nonverbal: bool
    speech_form: str | None
    dialogue_context: str | None


@dataclass(frozen=True)
class Corpus:
    version: int
    title: str
    speaker_agnostic: bool
    target_audio_minutes: float
    notes: tuple[str, ...]
    styles: Mapping[str, Mapping[str, Any]]
    items: tuple[Prompt, ...]


def _prompt_from_dict(row: Mapping[str, Any]) -> Prompt:
    return Prompt(
        id=str(row.get("id", "")).strip(),
        block=str(row.get("block", "")).strip(),
        block_label=str(row.get("block_label", "")).strip(),
        tier=int(row.get("tier", 0)),
        style=str(row.get("style", "")).strip(),
        target_sec=float(row.get("target_sec", 0)),
        text=str(row.get("text", "")).strip(),
        note=str(row.get("note", "")).strip(),
        source=None if row.get("source") is None else str(row["source"]).strip(),
        nonverbal=bool(row.get("nonverbal", False)),
        speech_form=(
            None
            if row.get("speech_form") is None
            else str(row["speech_form"]).strip()
        ),
        dialogue_context=(
            None
            if row.get("dialogue_context") is None
            else str(row["dialogue_context"]).strip()
        ),
    )


def load_corpus(path: Path) -> Corpus:
    """Load the canonical public recording pack."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return Corpus(
        version=int(payload.get("version", 0)),
        title=str(payload.get("title", "")).strip(),
        speaker_agnostic=bool(payload.get("speaker_agnostic", False)),
        target_audio_minutes=float(payload.get("target_audio_minutes", 0)),
        notes=tuple(str(note).strip() for note in payload.get("notes", [])),
        styles=dict(payload.get("styles", {})),
        items=tuple(_prompt_from_dict(row) for row in payload.get("items", [])),
    )


def validate_corpus(corpus: Corpus) -> list[str]:
    """Return concrete validation failures without mutating the pack."""
    errors: list[str] = []
    ids = [item.id for item in corpus.items]
    if corpus.version != 3:
        errors.append("version must be 3")
    if not corpus.speaker_agnostic:
        errors.append("speaker_agnostic must be true")
    if len(corpus.items) != 156:
        errors.append(f"expected 156 items, found {len(corpus.items)}")
    if len(set(ids)) != len(ids):
        errors.append("item ids must be unique")
    if {item.tier for item in corpus.items} != {1, 2, 3}:
        errors.append("tiers must be exactly 1, 2 and 3")

    declared = set(corpus.styles)
    for style, config in corpus.styles.items():
        for field in ("label", "role", "direction"):
            if not str(config.get(field, "")).strip():
                errors.append(f"style {style} is missing {field}")
    for item in corpus.items:
        if not item.id:
            errors.append("an item has an empty id")
        if not item.block or not item.block_label:
            errors.append(f"item {item.id or '<missing>'} has no block label")
        if item.style not in declared | SPECIAL_STYLES:
            errors.append(f"item {item.id} uses undeclared style {item.style}")
        if not item.text:
            errors.append(f"item {item.id} has no recording text")
        if item.target_sec <= 0:
            errors.append(f"item {item.id} has a non-positive target duration")
        if (item.source or "").lower().startswith("public domain") and "," not in (
            item.source or ""
        ):
            errors.append(f"item {item.id} has incomplete public-domain attribution")
        if item.speech_form not in {None, "dialogue_turn"}:
            errors.append(f"item {item.id} has unsupported speech form")
        if item.speech_form == "dialogue_turn":
            if not item.dialogue_context:
                errors.append(f"item {item.id} has no dialogue context")
            elif "single speaker" not in item.dialogue_context.casefold():
                errors.append(f"item {item.id} dialogue context is not single-speaker")
        elif item.dialogue_context:
            errors.append(f"item {item.id} has dialogue context without a dialogue turn")

    serialized = json.dumps(
        {
            "title": corpus.title,
            "notes": corpus.notes,
            "styles": corpus.styles,
            "items": [item.__dict__ for item in corpus.items],
        },
        ensure_ascii=False,
    )
    if PRIVATE_IDENTITY_PATTERN.search(serialized):
        errors.append("corpus contains a private identity marker")
    if any(pattern.search(serialized) for pattern in ABSOLUTE_PATH_PATTERNS):
        errors.append("corpus contains an absolute user-profile path")
    return errors


def _render_prompt(item: Prompt, heading_level: int = 3) -> list[str]:
    lines = [
        f"{'#' * heading_level} `{item.id}`: {item.block_label}",
        "",
        f"Tier {item.tier}. Style: `{item.style}`. Target: {item.target_sec:g} seconds.",
        "",
    ]
    if item.note:
        lines.extend([f"Direction: {item.note}", ""])
    if item.speech_form == "dialogue_turn":
        lines.extend(
            [
                "Speech form: single-speaker dialogue turn. Record only the displayed turn.",
                "",
                f"Dialogue context: {item.dialogue_context}",
                "",
            ]
        )
    lines.extend([f"> {item.text.replace(chr(10), ' ')}", ""])
    if item.source:
        lines.extend([f"Source: {item.source}", ""])
    return lines


def render_full_script(corpus: Corpus) -> str:
    """Render every prompt in recording order as one readable document."""
    lines = [
        "# Complete voice capture script",
        "",
        (
            f"{len(corpus.items)} prompts across three tiers. The estimated recorded "
            f"audio is {corpus.target_audio_minutes:g} minutes."
        ),
        "",
        "Use the exact item IDs as filenames or ledger keys. Keep recordings private.",
        "",
    ]
    current_block = None
    for item in corpus.items:
        if item.block != current_block:
            current_block = item.block
            lines.extend([f"## Block {item.block}: {item.block_label}", ""])
        lines.extend(_render_prompt(item))
    return "\n".join(lines).rstrip() + "\n"


def render_block(corpus: Corpus, block: str) -> str:
    """Render one complete block from the canonical pack."""
    items = [item for item in corpus.items if item.block == block]
    if not items:
        raise ValueError(f"unknown block: {block}")
    lines = [f"# Block {block}: {items[0].block_label}", ""]
    for item in items:
        lines.extend(_render_prompt(item, heading_level=2))
    return "\n".join(lines).rstrip() + "\n"


def write_views(corpus: Corpus, output_dir: Path) -> None:
    """Write the human-readable script, block views, and emotion catalogue."""
    errors = validate_corpus(corpus)
    if errors:
        raise ValueError("; ".join(errors))

    output_dir = Path(output_dir)
    parts_dir = output_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "full-recording-script.md").write_text(
        render_full_script(corpus), encoding="utf-8", newline="\n"
    )

    for block in dict.fromkeys(item.block for item in corpus.items):
        label = next(item.block_label for item in corpus.items if item.block == block)
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        (parts_dir / f"{block.lower()}-{slug}.md").write_text(
            render_block(corpus, block), encoding="utf-8", newline="\n"
        )

    with (output_dir / "emotion-catalog.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["style", "label", "role", "direction"],
            lineterminator="\n",
        )
        writer.writeheader()
        for style, config in corpus.styles.items():
            writer.writerow(
                {
                    "style": style,
                    "label": config["label"],
                    "role": config["role"],
                    "direction": config["direction"],
                }
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    corpus = load_corpus(args.source)
    write_views(corpus, args.output_dir)
    print(f"validated and rendered {len(corpus.items)} prompts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
