from __future__ import annotations

import csv
import json
import re
from dataclasses import replace
from pathlib import Path

from voice_replication_kit.corpus import (
    load_corpus,
    render_block,
    render_full_script,
    validate_corpus,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "corpus" / "recording-script.json"


def test_recording_pack_is_complete_and_speaker_agnostic() -> None:
    corpus = load_corpus(CORPUS_PATH)

    assert corpus.version == 3
    assert corpus.speaker_agnostic is True
    assert len(corpus.items) == 156
    assert len({item.id for item in corpus.items}) == 156
    assert {item.tier for item in corpus.items} == {1, 2, 3}
    assert validate_corpus(corpus) == []


def test_recording_pack_has_explicit_single_speaker_dialogue_turns() -> None:
    corpus = load_corpus(CORPUS_PATH)

    dialogue_turns = [
        item for item in corpus.items if item.speech_form == "dialogue_turn"
    ]

    assert {item.id for item in dialogue_turns} == {
        "F-08",
        "K-warm-1",
        "K-warm-2",
        "K-empathetic-2",
    }
    assert all(item.dialogue_context for item in dialogue_turns)
    assert all("single speaker" in item.dialogue_context.casefold() for item in dialogue_turns)
    assert all(
        item.speech_form in {None, "dialogue_turn"} for item in corpus.items
    )


def test_recording_pack_text_does_not_claim_stale_private_workflows_or_results() -> None:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def string_values(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [text for item in value for text in string_values(item)]
        if isinstance(value, dict):
            return [text for item in value.values() for text in string_values(item)]
        return []

    public_text = "\n".join(string_values(payload)).casefold()
    for forbidden in (
        "chatterbox",
        "ingest.py",
        "winning neutral clip",
        "clone",
        "model hears",
        "model needs",
        "teaches the model",
        "gives the model",
        "testing",
        "first attempt",
        "indistinguishable from you",
    ):
        assert forbidden not in public_text


def test_rendered_dialogue_turns_tell_each_reader_to_record_one_turn() -> None:
    corpus = load_corpus(CORPUS_PATH)
    rendered = render_full_script(corpus)

    assert rendered.count("Speech form: single-speaker dialogue turn.") == 4
    assert rendered.count("Record only the displayed turn.") == 4
    for item in corpus.items:
        if item.speech_form == "dialogue_turn":
            assert item.dialogue_context in rendered


def test_recording_pack_contains_every_declared_emotion() -> None:
    corpus = load_corpus(CORPUS_PATH)
    declared = set(corpus.styles)
    item_styles = {item.style for item in corpus.items}

    assert declared == {
        "anger_fierce",
        "awe_wonder",
        "curious_questioning",
        "empathetic_calm",
        "emphatic_punchy",
        "excited_energetic",
        "narration_neutral",
        "playful_wry",
        "serious_authoritative",
        "sorrow_grief",
        "suspense_hushed",
        "tender_intimate",
        "triumphant_declaratory",
        "warm_friendly",
    }
    assert declared <= item_styles
    assert item_styles - declared == {"calibration", "mixed", "paralinguistic"}


def test_every_prompt_has_speakable_text_or_a_nonverbal_instruction() -> None:
    corpus = load_corpus(CORPUS_PATH)

    incomplete = [
        item.id for item in corpus.items if not item.text.strip() and not item.nonverbal
    ]

    assert incomplete == []


def test_public_domain_passages_keep_source_attribution() -> None:
    corpus = load_corpus(CORPUS_PATH)
    attributed = [
        item for item in corpus.items if (item.source or "").lower().startswith("public domain")
    ]

    assert len(attributed) == 9
    assert all(item.text.strip() for item in attributed)
    assert all("," in (item.source or "") for item in attributed)


def test_corpus_contains_no_private_identity_markers_or_absolute_paths() -> None:
    text = CORPUS_PATH.read_text(encoding="utf-8")

    assert re.search(
        r"(?i)<(?:speaker|evaluator)-name>|(?:speaker|evaluator)[ _-]?id", text
    ) is None
    assert re.search(r"(?i)\b[A-Z]:\\Users\\", text) is None
    assert re.search(r"(?i)(?<![\w.-])/(?:home|Users)/[^/\s]+/", text) is None


def test_validator_rejects_explicit_private_identity_markers() -> None:
    corpus = load_corpus(CORPUS_PATH)

    assert "corpus contains a private identity marker" in validate_corpus(
        replace(corpus, title="Capture pack for <speaker-name>")
    )


def test_human_readable_views_cover_the_complete_pack() -> None:
    corpus = load_corpus(CORPUS_PATH)
    script = (ROOT / "corpus" / "full-recording-script.md").read_text(encoding="utf-8")
    part_files = sorted((ROOT / "corpus" / "parts").glob("*.md"))
    combined_parts = "\n".join(path.read_text(encoding="utf-8") for path in part_files)

    assert len(part_files) == 12
    assert all(f"`{item.id}`" in script for item in corpus.items)
    assert all(f"`{item.id}`" in combined_parts for item in corpus.items)


def test_prompt_headings_match_each_rendered_document_hierarchy() -> None:
    corpus = load_corpus(CORPUS_PATH)

    full_script = render_full_script(corpus)
    standalone_block = render_block(corpus, "A")

    assert "\n### `A-01`: Calibration\n" in full_script
    assert "\n## `A-01`: Calibration\n" in standalone_block
    assert "\n### `A-01`: Calibration\n" not in standalone_block


def test_emotion_catalog_matches_declared_styles() -> None:
    corpus = load_corpus(CORPUS_PATH)
    with (ROOT / "corpus" / "emotion-catalog.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))

    assert list(rows[0]) == ["style", "label", "role", "direction"]
    assert len(rows) == 14
    assert {row["style"] for row in rows} == set(corpus.styles)
