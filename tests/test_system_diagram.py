from __future__ import annotations

from pathlib import Path
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from tools import build_diagrams


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


def _png_chunks(data: bytes) -> list[str]:
    chunks: list[str] = []
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8].decode("ascii")
        chunks.append(chunk_type)
        offset += 12 + length
        if chunk_type == "IEND":
            break
    return chunks


def _element_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def test_only_the_approved_diagram_family_is_published() -> None:
    assert {path.name for path in ASSETS.glob("voice-replication-*.html")} == {
        f"{SLUG}.html"
    }
    assert {path.name for path in ASSETS.glob("voice-replication-*.svg")} == {
        f"{SLUG}.svg"
    }
    assert {path.name for path in ASSETS.glob("voice-replication-*.png")} == {
        f"{SLUG}.png"
    }
    assert not (ASSETS / "voice-replication-diagrams.json").exists()
    assert not (ROOT / "docs" / "diagram-candidates.md").exists()
    for old_slug in OLD_SLUGS:
        assert not any(ASSETS.glob(f"{old_slug}.*"))


def test_png_is_native_size_and_contains_no_text_metadata() -> None:
    data = PNG_PATH.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (1600, 1000)
    chunks = _png_chunks(data)
    assert chunks[-1] == "IEND"
    assert not {"tEXt", "zTXt", "iTXt", "eXIf"}.intersection(chunks)


def test_svg_tells_the_record_once_and_reuse_story() -> None:
    root = ET.fromstring(SVG_PATH.read_text(encoding="utf-8"))
    visible_copy = {
        element.attrib.get("data-copy", _element_text(element))
        for element in root.iter()
        if element.tag.endswith("text")
    }
    assert {
        "Create your private voice once, then use it for every new script.",
        "Record your voice once",
        "Reusable private voice package",
        "Create audio from each new script",
        "Use the same package for the next script.",
        "Everything after this line stays private.",
        "Never put recordings, the voice package, or generated audio in Git.",
        "gitramnag / voice-replication-kit",
    }.issubset(visible_copy)

    repeat = next(
        element
        for element in root.iter()
        if element.attrib.get("data-repeat-loop") == "true"
    )
    assert repeat.attrib["data-source"] == "create"
    assert repeat.attrib["data-target"] == "package"
    assert repeat.attrib["data-target"] != "record"


def test_minimum_system_is_quiet_separate_and_vendor_neutral() -> None:
    root = ET.fromstring(SVG_PATH.read_text(encoding="utf-8"))
    system = next(
        element
        for element in root.iter()
        if element.attrib.get("data-geometry-id") == "minimum-system"
    )
    copy = {
        element.attrib["data-copy"]
        for element in system.iter()
        if "data-copy" in element.attrib
    }
    assert copy == {
        "Minimum system",
        "64-bit Linux or WSL2",
        "Python 3.10, Git, and Bash",
        "16 GB RAM",
        "20 GB free disk",
        "GPU: 8 GB VRAM starting point",
        "Compatible driver and runtime",
    }
    assert not any(element.attrib.get("data-info-panel") for element in system.iter())
    assert sum(
        element.attrib.get("data-system-rule") == "true" for element in system.iter()
    ) == 1
    lowered = " ".join(copy).lower()
    assert "for private audio" not in lowered
    assert "nvidia" not in lowered
    assert "amd" not in lowered


def test_html_and_svg_are_accessible_static_and_self_contained() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    svg = SVG_PATH.read_text(encoding="utf-8")
    for markup in (html, svg):
        lowered = markup.lower()
        assert "<script" not in lowered
        assert "@import" not in lowered
        assert not re.search(r"(?:href|src)=[\"']https?://", markup, re.IGNORECASE)
        assert "data:font/woff2;base64," in markup
        assert "role=\"img\"" in markup
        assert "aria-labelledby=\"studio-journey-title studio-journey-desc\"" in markup

    svg_root = ET.fromstring(svg)
    children = list(svg_root)
    assert children[0].tag.endswith("title")
    assert children[1].tag.endswith("desc")
    assert children[0].attrib["id"] == "studio-journey-title"
    assert children[1].attrib["id"] == "studio-journey-desc"


def test_warning_and_footer_share_the_small_bottom_baseline() -> None:
    root = ET.fromstring(SVG_PATH.read_text(encoding="utf-8"))
    text_by_copy = {
        element.attrib.get("data-copy"): element
        for element in root.iter()
        if element.tag.endswith("text") and element.attrib.get("data-copy")
    }
    warning = text_by_copy[
        "Never put recordings, the voice package, or generated audio in Git."
    ]
    footer = text_by_copy["gitramnag / voice-replication-kit"]
    assert warning.attrib["y"] == footer.attrib["y"] == "930"
    assert "footer-note" in warning.attrib["class"]
    assert "footer-note" in footer.attrib["class"]


def test_readme_architecture_and_design_point_to_the_approved_diagram() -> None:
    for relative in ("README.md", "docs/architecture.md", "DESIGN.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert SLUG in text, relative
        assert "diagram-candidates.md" not in text, relative
        assert "three candidates" not in text.lower(), relative


def test_release_gate_accepts_the_committed_assets() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_diagrams.py"), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "approved diagram assets are current" in completed.stdout


def test_release_gate_functions_reject_regressions() -> None:
    svg = SVG_PATH.read_text(encoding="utf-8")
    html = HTML_PATH.read_text(encoding="utf-8")
    png = PNG_PATH.read_bytes()
    build_diagrams.validate_svg(svg)
    build_diagrams.validate_html(html)
    build_diagrams.validate_png(png)

    with pytest.raises(ValueError, match="reusable package"):
        build_diagrams.validate_svg(
            svg.replace(
                'data-source="create" data-target="package"',
                'data-source="create" data-target="create"',
                1,
            )
        )
    with pytest.raises(ValueError, match="network"):
        build_diagrams.validate_html(
            html.replace(
                "</head>",
                '<link rel="stylesheet" href="https://example.test/x.css"></head>',
                1,
            )
        )
    with pytest.raises(ValueError, match="1600 by 1000"):
        altered = bytearray(png)
        altered[16:20] = struct.pack(">I", 1599)
        build_diagrams.validate_png(bytes(altered))
