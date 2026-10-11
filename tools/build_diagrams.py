#!/usr/bin/env python3
"""Validate the approved public diagram assets without retaining build sources."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
SLUG = "voice-replication-studio-journey"
HTML_PATH = ASSETS / f"{SLUG}.html"
SVG_PATH = ASSETS / f"{SLUG}.svg"
PNG_PATH = ASSETS / f"{SLUG}.png"
OLD_SLUGS = (
    "voice-replication-one-view-transit",
    "voice-replication-one-view-control-plane",
    "voice-replication-one-view-field-atlas",
)
REQUIRED_COPY = (
    "Create your private voice once, then use it for every new script.",
    "Record your voice once",
    "Reusable private voice package",
    "Create audio from each new script",
    "Use the same package for the next script.",
    "Everything after this line stays private.",
    "Never put recordings, the voice package, or generated audio in Git.",
    "Minimum system",
    "64-bit Linux or WSL2",
    "Python 3.10, Git, and Bash",
    "16 GB RAM",
    "20 GB free disk",
    "GPU: 8 GB VRAM starting point",
    "Compatible driver and runtime",
    "gitramnag / voice-replication-kit",
)
NETWORK_ATTRIBUTE_RE = re.compile(r"(?:href|src)=[\"']https?://", re.IGNORECASE)
METADATA_CHUNKS = {"tEXt", "zTXt", "iTXt", "eXIf"}


def _reject_active_content(markup: str) -> None:
    lowered = markup.lower()
    if "<script" in lowered:
        raise ValueError("scripts are not allowed in public diagram assets")
    if "@import" in lowered or NETWORK_ATTRIBUTE_RE.search(markup):
        raise ValueError("network resources are not allowed in public diagram assets")
    if "data:font/woff2;base64," not in markup:
        raise ValueError("approved embedded fonts are missing")


def validate_html(markup: str) -> None:
    _reject_active_content(markup)
    if '<meta name="viewport" content="width=device-width, initial-scale=1">' not in markup:
        raise ValueError("responsive viewport metadata is missing")
    if 'viewBox="0 0 1600 1000"' not in markup:
        raise ValueError("HTML diagram must use the 1600 by 1000 frame")
    if 'role="img"' not in markup:
        raise ValueError("HTML diagram is missing the accessible image role")
    for item in REQUIRED_COPY:
        if item not in markup:
            raise ValueError(f"HTML diagram is missing approved copy: {item}")


def validate_svg(markup: str) -> None:
    _reject_active_content(markup)
    try:
        root = ET.fromstring(markup)
    except ET.ParseError as error:
        raise ValueError(f"standalone SVG is not well formed: {error}") from error
    if root.attrib.get("viewBox") != "0 0 1600 1000":
        raise ValueError("SVG diagram must use the 1600 by 1000 frame")
    if root.attrib.get("role") != "img":
        raise ValueError("SVG diagram is missing the accessible image role")
    children = list(root)
    if len(children) < 2 or not children[0].tag.endswith("title") or not children[1].tag.endswith("desc"):
        raise ValueError("SVG title and description must be its first two children")
    if root.attrib.get("aria-labelledby") != "studio-journey-title studio-journey-desc":
        raise ValueError("SVG accessible labels do not resolve to the approved IDs")
    for item in REQUIRED_COPY:
        if item not in markup:
            raise ValueError(f"SVG diagram is missing approved copy: {item}")

    repeat = [
        element
        for element in root.iter()
        if element.attrib.get("data-repeat-loop") == "true"
    ]
    if len(repeat) != 1:
        raise ValueError("SVG must contain one reusable-package return")
    if repeat[0].attrib.get("data-source") != "create" or repeat[0].attrib.get("data-target") != "package":
        raise ValueError("repeat flow must return from audio creation to the reusable package")
    if any(element.attrib.get("data-info-panel") for element in root.iter()):
        raise ValueError("minimum-system information must not use a panel")
    if "For private audio creation." in markup:
        raise ValueError("retired minimum-system subheading remains")
    if re.search(r"\b(?:NVIDIA|AMD)\b", markup, re.IGNORECASE):
        raise ValueError("minimum-system GPU wording must remain vendor-neutral")


def _png_chunks(data: bytes) -> list[str]:
    chunks: list[str] = []
    offset = 8
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("PNG has a truncated chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8].decode("ascii", errors="strict")
        next_offset = offset + 12 + length
        if next_offset > len(data):
            raise ValueError("PNG has a truncated chunk payload")
        chunks.append(chunk_type)
        offset = next_offset
        if chunk_type == "IEND":
            break
    return chunks


def validate_png(data: bytes) -> None:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        raise ValueError("approved PNG signature is missing")
    if struct.unpack(">II", data[16:24]) != (1600, 1000):
        raise ValueError("PNG diagram must be exactly 1600 by 1000")
    chunks = _png_chunks(data)
    if not chunks or chunks[-1] != "IEND":
        raise ValueError("PNG does not end with IEND")
    metadata = METADATA_CHUNKS.intersection(chunks)
    if metadata:
        raise ValueError(f"PNG contains metadata chunks: {sorted(metadata)}")


def validate_asset_set() -> None:
    expected = {
        f"{SLUG}.html",
        f"{SLUG}.svg",
        f"{SLUG}.png",
    }
    actual = {
        path.name
        for pattern in ("voice-replication-*.html", "voice-replication-*.svg", "voice-replication-*.png")
        for path in ASSETS.glob(pattern)
    }
    if actual != expected:
        raise ValueError(f"diagram asset set differs; expected={sorted(expected)}, actual={sorted(actual)}")
    if (ASSETS / "voice-replication-diagrams.json").exists():
        raise ValueError("retired diagram semantic source remains")
    for old_slug in OLD_SLUGS:
        if any(ASSETS.glob(f"{old_slug}.*")):
            raise ValueError(f"retired diagram remains: {old_slug}")


def check_assets() -> None:
    validate_asset_set()
    validate_html(HTML_PATH.read_text(encoding="utf-8"))
    validate_svg(SVG_PATH.read_text(encoding="utf-8"))
    validate_png(PNG_PATH.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the approved static assets; retained for release-script compatibility",
    )
    parser.parse_args(argv)
    try:
        check_assets()
    except (OSError, ValueError) as error:
        print(f"diagram asset check failed: {error}", file=sys.stderr)
        return 1
    print("approved diagram assets are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
