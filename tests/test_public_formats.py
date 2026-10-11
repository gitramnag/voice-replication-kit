from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from pathlib import Path, PurePosixPath
import re
import struct
import warnings
import zipfile
import zlib
from xml.etree import ElementTree

import pytest

from voice_replication_kit.public_formats import (
    detect_signature,
    validate_blank_scorecard,
    validate_public_png,
)


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SCORECARD = ROOT / "evaluation" / "voice-evaluation-scorecard.xlsx"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _rewrite_xlsx_entries(
    data: bytes, replacements: dict[str, Callable[[bytes], bytes]]
) -> bytes:
    output = BytesIO()
    with (
        zipfile.ZipFile(BytesIO(data)) as source,
        zipfile.ZipFile(output, "w") as target,
    ):
        for info in source.infolist():
            payload = source.read(info)
            if info.filename in replacements:
                payload = replacements[info.filename](payload)
            target.writestr(info, payload)
    return output.getvalue()


def _copy_xlsx_entries(
    data: bytes,
    *,
    additions: tuple[tuple[str, bytes], ...] = (),
    omissions: frozenset[str] = frozenset(),
) -> bytes:
    output = BytesIO()
    with (
        zipfile.ZipFile(BytesIO(data)) as source,
        zipfile.ZipFile(output, "w") as target,
    ):
        for info in source.infolist():
            if info.filename not in omissions:
                target.writestr(info, source.read(info))
        for name, payload in additions:
            target.writestr(name, payload)
    return output.getvalue()


def _mutate_xml_entry(
    data: bytes,
    entry: str,
    mutation: Callable[[ElementTree.Element], None],
) -> bytes:
    def rewrite(payload: bytes) -> bytes:
        root = ElementTree.fromstring(payload)
        mutation(root)
        return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)

    return _rewrite_xlsx_entries(data, {entry: rewrite})


def _cell(root: ElementTree.Element, reference: str) -> ElementTree.Element:
    cell = root.find(f".//{{{MAIN_NS}}}c[@r='{reference}']")
    assert cell is not None
    return cell


def _png(
    *extra_chunks: tuple[bytes, bytes],
    corrupt_crc: bool = False,
    bit_depth: int = 8,
    color_type: int = 6,
    after_idat: tuple[tuple[bytes, bytes], ...] = (),
) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if corrupt_crc and kind == b"IDAT":
            checksum ^= 1
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

    ihdr = struct.pack(">IIBBBBB", 1, 1, bit_depth, color_type, 0, 0, 0)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    pixels = zlib.compress(b"\x00" + bytes((channels * bit_depth + 7) // 8))
    return b"\x89PNG\r\n\x1a\n" + b"".join(
        [chunk(b"IHDR", ihdr)]
        + [chunk(kind, payload) for kind, payload in extra_chunks]
        + [chunk(b"IDAT", pixels)]
        + [chunk(kind, payload) for kind, payload in after_idat]
        + [chunk(b"IEND", b"")]
    )


def _xlsx(
    *,
    sheet_state: str = "",
    sheet_xml: str | None = None,
    extra_entries: list[tuple[str, bytes]] | None = None,
    relationship: str = "",
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    workbook = f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="Ratings" sheetId="2" r:id="rId1"{sheet_state}/></sheets>
</workbook>""".encode()
    relationships = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
 {relationship}
</Relationships>""".encode()
    root_relationships = b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    content_types = b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="xml" ContentType="application/xml"/>
</Types>"""
    worksheet = (sheet_xml or """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <sheetData><row r="2"><c r="F2"/></row></sheetData>
</worksheet>""").encode()
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_relationships)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet2.xml", worksheet)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, data in extra_entries or []:
                archive.writestr(name, data)
    return stream.getvalue()


def _patch_central_sizes(data: bytes, sizes: dict[str, int]) -> bytes:
    patched = bytearray(data)
    offset = 0
    while True:
        offset = patched.find(b"PK\x01\x02", offset)
        if offset < 0:
            break
        name_length = struct.unpack_from("<H", patched, offset + 28)[0]
        extra_length = struct.unpack_from("<H", patched, offset + 30)[0]
        comment_length = struct.unpack_from("<H", patched, offset + 32)[0]
        name = bytes(patched[offset + 46 : offset + 46 + name_length]).decode()
        if name in sizes:
            struct.pack_into("<I", patched, offset + 20, sizes[name])
            struct.pack_into("<I", patched, offset + 24, sizes[name])
        offset += 46 + name_length + extra_length + comment_length
    return bytes(patched)


def _mark_entry_encrypted(data: bytes, target: str) -> bytes:
    patched = bytearray(data)
    central = 0
    while True:
        central = patched.find(b"PK\x01\x02", central)
        if central < 0:
            raise AssertionError("ZIP entry was not found")
        name_length = struct.unpack_from("<H", patched, central + 28)[0]
        name = bytes(patched[central + 46 : central + 46 + name_length]).decode()
        if name == target:
            local = struct.unpack_from("<I", patched, central + 42)[0]
            central_flags = struct.unpack_from("<H", patched, central + 8)[0]
            local_flags = struct.unpack_from("<H", patched, local + 6)[0]
            struct.pack_into("<H", patched, central + 8, central_flags | 1)
            struct.pack_into("<H", patched, local + 6, local_flags | 1)
            break
        central += 46 + name_length
    return bytes(patched)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"RIFF\x00\x00\x00\x00WAVE", "riff-container"),
        (b"PK\x03\x04", "zip-container"),
        (b"\x80\x04fixture", "python-pickle"),
        (b"SQLite format 3\x00", "sqlite-database"),
        (b"\x7fELF", "elf-binary"),
        (b"MZ", "windows-binary"),
        (b"GGUF", "gguf-model"),
        (b"BZh", "bzip2-archive"),
        (b"\x1f\x8b", "gzip-archive"),
        (b"7z\xbc\xaf'\x1c", "7z-archive"),
        (b"Rar!\x1a\x07\x01\x00", "rar-archive"),
        (b"\xfe\xed\xfa\xce", "mach-o-binary"),
        (b"\x00" * 257 + b"ustar\x0000", "tar-archive"),
        (b"plain text", None),
    ],
)
def test_detect_signature_identifies_disguised_payloads(
    data: bytes, expected: str | None
) -> None:
    assert detect_signature(data) == expected


def test_public_png_accepts_a_real_metadata_free_image() -> None:
    assert validate_public_png(PurePosixPath("diagram.png"), _png()) == []


@pytest.mark.parametrize("chunk", [b"tEXt", b"zTXt", b"iTXt", b"eXIf"])
def test_public_png_rejects_text_and_exif_chunks(chunk: bytes) -> None:
    findings = validate_public_png(
        PurePosixPath("diagram.png"), _png((chunk, b"private metadata"))
    )
    assert any(item.code == "unsafe-png" for item in findings)


def test_public_png_fails_closed_on_a_bad_chunk_checksum() -> None:
    findings = validate_public_png(
        PurePosixPath("diagram.png"), _png(corrupt_crc=True)
    )
    assert any(item.code == "malformed-png" for item in findings)


@pytest.mark.parametrize(
    ("chunk", "payload"),
    [
        (b"sRGB", b"\x04"),
        (b"gAMA", b"arbitrary"),
        (b"cHRM", b"\x00" * 32),
        (b"pHYs", struct.pack(">IIB", 3780, 3780, 2)),
        (b"tRNS", b"\x00\x00"),
    ],
)
def test_public_png_rejects_malformed_allowed_ancillary_chunks(
    chunk: bytes, payload: bytes
) -> None:
    findings = validate_public_png(
        PurePosixPath("diagram.png"), _png((chunk, payload))
    )
    assert any(item.code == "malformed-png" for item in findings)


@pytest.mark.parametrize(
    "chunks",
    [
        ((b"sRGB", b"\x00"), (b"sRGB", b"\x00")),
        ((b"gAMA", struct.pack(">I", 45455)), (b"gAMA", struct.pack(">I", 45455))),
        (
            (
                b"cHRM",
                struct.pack(
                    ">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000
                ),
            ),
        )
        * 2,
        ((b"pHYs", struct.pack(">IIB", 3780, 3780, 1)),) * 2,
    ],
)
def test_public_png_rejects_duplicate_singleton_ancillary_chunks(
    chunks: tuple[tuple[bytes, bytes], ...]
) -> None:
    findings = validate_public_png(PurePosixPath("diagram.png"), _png(*chunks))
    assert any(item.code == "malformed-png" for item in findings)


@pytest.mark.parametrize(
    ("chunk", "payload"),
    [
        (b"sRGB", b"\x00"),
        (b"gAMA", struct.pack(">I", 45455)),
        (
            b"cHRM",
            struct.pack(
                ">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000
            ),
        ),
        (b"pHYs", struct.pack(">IIB", 3780, 3780, 1)),
        (b"tRNS", b"\x00\x00"),
    ],
)
def test_public_png_rejects_ancillary_chunks_after_image_data(
    chunk: bytes, payload: bytes
) -> None:
    image = _png(after_idat=((chunk, payload),), color_type=0)
    findings = validate_public_png(PurePosixPath("diagram.png"), image)
    assert any(item.code == "malformed-png" for item in findings)


def test_public_png_accepts_semantically_valid_ancillary_chunks() -> None:
    chunks = (
        (b"sRGB", b"\x00"),
        (b"gAMA", struct.pack(">I", 45455)),
        (
            b"cHRM",
            struct.pack(
                ">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000
            ),
        ),
        (b"pHYs", struct.pack(">IIB", 3780, 3780, 1)),
        (b"tRNS", b"\x00\x00"),
    )
    assert validate_public_png(
        PurePosixPath("diagram.png"),
        _png(*chunks, color_type=0),
    ) == []


def test_indexed_png_rejects_a_palette_larger_than_its_bit_depth() -> None:
    palette = bytes(range(9))
    findings = validate_public_png(
        PurePosixPath("diagram.png"),
        _png((b"PLTE", palette), bit_depth=1, color_type=3),
    )

    assert any(item.code == "malformed-png" for item in findings)


def test_blank_scorecard_accepts_a_real_empty_open_xml_package() -> None:
    assert validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        PUBLIC_SCORECARD.read_bytes(),
    ) == []


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        (
            "xl/worksheets/sheet99.xml",
            b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>private value</t></is></c></row></sheetData></worksheet>',
        ),
        (
            "xl/tables/table99.xml",
            b'<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" name="PrivateValue"/>',
        ),
        (
            "xl/theme/theme99.xml",
            b'<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="private value"/>',
        ),
        (
            "xl/sharedStrings.xml",
            b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>private value</t></si></sst>',
        ),
    ],
)
def test_blank_scorecard_rejects_surplus_allowed_family_parts(
    name: str, payload: bytes
) -> None:
    malicious = _copy_xlsx_entries(
        PUBLIC_SCORECARD.read_bytes(), additions=((name, payload),)
    )

    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )

    assert any(item.code == "unsafe-xlsx" for item in findings)


@pytest.mark.parametrize(
    "name",
    [
        "docProps/core.xml",
        "xl/styles.xml",
        "xl/worksheets/sheet1.xml",
        "xl/tables/table1.xml",
    ],
)
def test_blank_scorecard_rejects_missing_expected_package_parts(name: str) -> None:
    malicious = _copy_xlsx_entries(
        PUBLIC_SCORECARD.read_bytes(), omissions=frozenset({name})
    )

    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )

    assert any(item.code == "unsafe-xlsx" for item in findings)


@pytest.mark.parametrize(
    ("entry", "reference", "replacement"),
    [
        ("xl/worksheets/sheet2.xml", "L2", None),
        ("xl/worksheets/sheet2.xml", "M51", "0"),
        ("xl/worksheets/sheet2.xml", "L101", None),
        ("xl/worksheets/sheet3.xml", "B2", "0"),
        ("xl/worksheets/sheet3.xml", "F8", "0"),
        ("xl/worksheets/sheet3.xml", "E15", None),
    ],
)
def test_blank_scorecard_rejects_formula_inventory_drift(
    entry: str, reference: str, replacement: str | None
) -> None:
    def mutate(root: ElementTree.Element) -> None:
        cell = _cell(root, reference)
        formula = cell.find(f"{{{MAIN_NS}}}f")
        assert formula is not None
        if replacement is None:
            cell.remove(formula)
        else:
            formula.text = replacement

    malicious = _mutate_xml_entry(PUBLIC_SCORECARD.read_bytes(), entry, mutate)
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )

    assert any(item.code == "unsafe-xlsx" for item in findings)


@pytest.mark.parametrize(
    ("entry", "reference"),
    [
        ("xl/worksheets/sheet2.xml", "A2"),
        ("xl/worksheets/sheet2.xml", "F51"),
        ("xl/worksheets/sheet2.xml", "L101"),
        ("xl/worksheets/sheet2.xml", "M51"),
        ("xl/worksheets/sheet2.xml", "N101"),
        ("xl/worksheets/sheet3.xml", "B2"),
        ("xl/worksheets/sheet3.xml", "G8"),
        ("xl/worksheets/sheet3.xml", "H15"),
    ],
)
def test_blank_scorecard_rejects_applied_cell_style_drift(
    entry: str, reference: str
) -> None:
    def mutate(root: ElementTree.Element) -> None:
        cell = _cell(root, reference)
        assert cell.attrib.get("s") != "0"
        cell.set("s", "0")

    malicious = _mutate_xml_entry(PUBLIC_SCORECARD.read_bytes(), entry, mutate)
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )

    assert any(item.code == "unsafe-xlsx" for item in findings)


@pytest.mark.parametrize(
    ("entry", "kind"),
    [
        ("xl/worksheets/sheet1.xml", "dimension"),
        ("xl/worksheets/sheet2.xml", "dimension"),
        ("xl/worksheets/sheet3.xml", "dimension"),
        ("xl/worksheets/sheet2.xml", "header-text"),
        ("xl/worksheets/sheet3.xml", "header-style"),
        ("xl/worksheets/sheet2.xml", "conditional-format"),
        ("xl/worksheets/sheet2.xml", "column-width"),
        ("xl/worksheets/sheet3.xml", "row-height"),
    ],
)
def test_blank_scorecard_rejects_visual_contract_drift(entry: str, kind: str) -> None:
    def mutate(root: ElementTree.Element) -> None:
        if kind == "dimension":
            dimension = root.find(f"{{{MAIN_NS}}}dimension")
            assert dimension is not None
            dimension.set("ref", "A1:A1")
        elif kind == "header-text":
            text = _cell(root, "A1").find(f".//{{{MAIN_NS}}}t")
            assert text is not None
            text.text = "Private heading"
        elif kind == "header-style":
            _cell(root, "H1").set("s", "0")
        elif kind == "conditional-format":
            conditional = root.find(f"{{{MAIN_NS}}}conditionalFormatting")
            assert conditional is not None
            conditional.set("sqref", "L2:L100")
        elif kind == "column-width":
            column = root.find(f"{{{MAIN_NS}}}cols/{{{MAIN_NS}}}col[@min='3']")
            assert column is not None
            column.set("width", "20")
        else:
            row = root.find(f".//{{{MAIN_NS}}}row[@r='15']")
            assert row is not None
            row.set("ht", "20")

    malicious = _mutate_xml_entry(PUBLIC_SCORECARD.read_bytes(), entry, mutate)
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )

    assert any(item.code == "unsafe-xlsx" for item in findings)


@pytest.mark.parametrize(
    "kind",
    ["named-style", "number-format", "table-style"],
)
def test_blank_scorecard_rejects_defined_style_drift(kind: str) -> None:
    def mutate(root: ElementTree.Element) -> None:
        if kind == "named-style":
            style = root.find(
                f"{{{MAIN_NS}}}cellStyles/{{{MAIN_NS}}}cellStyle[@name='Calculated']"
            )
            assert style is not None
            style.set("name", "Changed")
        elif kind == "number-format":
            number_format = root.find(
                f"{{{MAIN_NS}}}numFmts/{{{MAIN_NS}}}numFmt[@numFmtId='164']"
            )
            assert number_format is not None
            number_format.set("formatCode", "0")
        else:
            table_style = root.find(
                f"{{{MAIN_NS}}}tableStyles/{{{MAIN_NS}}}tableStyle"
            )
            assert table_style is not None
            table_style.set("name", "Changed")

    malicious = _mutate_xml_entry(
        PUBLIC_SCORECARD.read_bytes(), "xl/styles.xml", mutate
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )

    assert any(item.code == "unsafe-xlsx" for item in findings)


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"extra_entries": [("xl/comments1.xml", b"<comments/>")]}, "unsafe-xlsx"),
        ({"extra_entries": [("xl/externalLinks/externalLink1.xml", b"<x/>")]}, "unsafe-xlsx"),
        ({"extra_entries": [("xl/media/private.wav", b"RIFF")]}, "unsafe-xlsx"),
        ({"extra_entries": [("xl/embeddings/object1.bin", b"private")]}, "unsafe-xlsx"),
        ({"sheet_state": ' state="hidden"'}, "unsafe-xlsx"),
        (
            {
                "relationship": '<Relationship Id="rId2" Type="link" Target="https://example.invalid/private" TargetMode="External"/>'
            },
            "unsafe-xlsx",
        ),
        (
            {
                "extra_entries": [
                    (
                        "docProps/core.xml",
                        b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>Private Person</dc:creator></cp:coreProperties>',
                    )
                ]
            },
            "unsafe-xlsx",
        ),
    ],
)
def test_blank_scorecard_rejects_private_open_xml_features(
    kwargs: dict[str, object], code: str
) -> None:
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), _xlsx(**kwargs)
    )
    assert any(item.code == code for item in findings)


def test_blank_scorecard_rejects_a_populated_score_cell() -> None:
    def populate(root: ElementTree.Element) -> None:
        value = ElementTree.SubElement(_cell(root, "F2"), f"{{{MAIN_NS}}}v")
        value.text = "5"

    malicious = _mutate_xml_entry(
        PUBLIC_SCORECARD.read_bytes(), "xl/worksheets/sheet2.xml", populate
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        malicious,
    )
    assert any(item.code == "populated-scorecard" for item in findings)


def test_blank_scorecard_rejects_a_cached_formula_result() -> None:
    def cache(root: ElementTree.Element) -> None:
        value = ElementTree.SubElement(_cell(root, "L2"), f"{{{MAIN_NS}}}v")
        value.text = "30"

    malicious = _mutate_xml_entry(
        PUBLIC_SCORECARD.read_bytes(), "xl/worksheets/sheet2.xml", cache
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        malicious,
    )
    assert any(item.code == "cached-formula-result" for item in findings)


def test_blank_scorecard_rejects_a_populated_renamed_score_sheet() -> None:
    def rename(payload: bytes) -> bytes:
        return payload.replace(b'name="Ratings"', b'name="Archive"', 1)

    def populate(payload: bytes) -> bytes:
        return re.sub(
            br'<c r="F2"([^>]*)/>',
            br'<c r="F2"\1 t="n"><v>5</v></c>',
            payload,
            count=1,
        )

    malicious = _rewrite_xlsx_entries(
        PUBLIC_SCORECARD.read_bytes(),
        {
            "xl/workbook.xml": rename,
            "xl/worksheets/sheet2.xml": populate,
        },
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )
    assert any(item.code == "populated-scorecard" for item in findings)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.replace(b'name="Ratings"', b'name="Archive"', 1),
        lambda data: re.sub(
            br'<sheet name="Instructions"[^>]*/>', b"", data, count=1
        ),
        lambda data: data.replace(
            b'<sheet name="Instructions" sheetId="1"',
            b'<sheet name="Extra" sheetId="1"',
            1,
        ),
        lambda data: data.replace(
            b'<sheet name="Instructions" sheetId="1"',
            b'<sheet name="Ratings" sheetId="1"',
            1,
        ),
        lambda data: data.replace(
            b'<sheet name="Ratings"',
            b'<sheet name="Temporary"',
            1,
        ).replace(b'<sheet name="Decisions"', b'<sheet name="Ratings"', 1)
        .replace(b'<sheet name="Temporary"', b'<sheet name="Decisions"', 1),
    ],
)
def test_blank_scorecard_rejects_sheet_inventory_drift(
    mutate: Callable[[bytes], bytes],
) -> None:
    malicious = _rewrite_xlsx_entries(
        PUBLIC_SCORECARD.read_bytes(), {"xl/workbook.xml": mutate}
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )
    assert any(item.code == "unsafe-xlsx" for item in findings)


def test_blank_scorecard_rejects_worksheet_relationship_drift() -> None:
    def mutate(payload: bytes) -> bytes:
        return payload.replace(
            b'Target="/xl/worksheets/sheet2.xml"',
            b'Target="/xl/worksheets/sheet3.xml"',
            1,
        )

    malicious = _rewrite_xlsx_entries(
        PUBLIC_SCORECARD.read_bytes(), {"xl/_rels/workbook.xml.rels": mutate}
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )
    assert any(item.code == "unsafe-xlsx" for item in findings)


@pytest.mark.parametrize(
    ("entry", "relationship_type", "target"),
    [
        (
            "_rels/.rels",
            "styles",
            "/xl/styles.xml",
        ),
        (
            "xl/_rels/workbook.xml.rels",
            "table",
            "/xl/tables/table1.xml",
        ),
        (
            "xl/worksheets/_rels/sheet2.xml.rels",
            "table",
            "/xl/tables/table2.xml",
        ),
        (
            "xl/worksheets/_rels/sheet3.xml.rels",
            "table",
            "/xl/tables/table1.xml",
        ),
    ],
)
def test_blank_scorecard_rejects_surplus_internal_relationships(
    entry: str,
    relationship_type: str,
    target: str,
) -> None:
    def add_relationship(payload: bytes) -> bytes:
        relationship = (
            '<Relationship Type="http://schemas.openxmlformats.org/'
            f'officeDocument/2006/relationships/{relationship_type}" '
            f'Target="{target}" Id="RReviewExtra" />'
        ).encode("ascii")
        return payload.replace(b"</Relationships>", relationship + b"</Relationships>")

    malicious = _rewrite_xlsx_entries(
        PUBLIC_SCORECARD.read_bytes(), {entry: add_relationship}
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )

    assert any(item.code == "unsafe-xlsx" for item in findings)


@pytest.mark.parametrize(
    ("entry", "old", "new"),
    [
        ("xl/worksheets/sheet2.xml", b'ySplit="1"', b'ySplit="2"'),
        ("xl/worksheets/sheet2.xml", b'sqref="D2:D101"', b'sqref="D2:D100"'),
        ("xl/tables/table1.xml", b'ref="A1:N101"', b'ref="A1:N100"'),
        (
            "xl/worksheets/_rels/sheet2.xml.rels",
            b'Target="/xl/tables/table1.xml"',
            b'Target="/xl/tables/table2.xml"',
        ),
    ],
)
def test_blank_scorecard_rejects_native_structure_drift(
    entry: str, old: bytes, new: bytes
) -> None:
    malicious = _rewrite_xlsx_entries(
        PUBLIC_SCORECARD.read_bytes(),
        {entry: lambda data: data.replace(old, new, 1)},
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )
    assert any(item.code == "unsafe-xlsx" for item in findings)


def test_blank_scorecard_rejects_zip_traversal_before_xml_parsing() -> None:
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        _xlsx(extra_entries=[("../private.txt", b"private")]),
    )
    assert any(item.code == "unsafe-xlsx-container" for item in findings)


def test_blank_scorecard_rejects_duplicate_zip_names() -> None:
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        _xlsx(extra_entries=[("xl/workbook.xml", b"<duplicate/>")]),
    )
    assert any(item.code == "unsafe-xlsx-container" for item in findings)


def test_blank_scorecard_rejects_a_zip_compression_bomb() -> None:
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        _xlsx(extra_entries=[("xl/worksheets/padding.xml", b"0" * 200_000)]),
    )
    assert any(item.code == "unsafe-xlsx-container" for item in findings)


def test_blank_scorecard_rejects_too_many_zip_entries() -> None:
    extras = [(f"xl/custom/part-{index}.xml", b"<part/>") for index in range(252)]
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        _xlsx(extra_entries=extras),
    )
    assert any(item.code == "unsafe-xlsx-container" for item in findings)


def test_blank_scorecard_rejects_an_oversized_zip_entry_from_metadata() -> None:
    name = "xl/custom/oversized.bin"
    malicious = _patch_central_sizes(
        _xlsx(extra_entries=[(name, b"x")], compression=zipfile.ZIP_STORED),
        {name: 20 * 1024 * 1024 + 1},
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )
    assert any(item.code == "unsafe-xlsx-container" for item in findings)


def test_blank_scorecard_rejects_excessive_total_uncompressed_size() -> None:
    names = [f"xl/custom/large-{index}.bin" for index in range(3)]
    malicious = _patch_central_sizes(
        _xlsx(
            extra_entries=[(name, b"x") for name in names],
            compression=zipfile.ZIP_STORED,
        ),
        {name: 18 * 1024 * 1024 for name in names},
    )
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), malicious
    )
    assert any(item.code == "unsafe-xlsx-container" for item in findings)


def test_blank_scorecard_rejects_an_encrypted_zip_entry() -> None:
    name = "xl/custom/encrypted.bin"
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        _mark_entry_encrypted(_xlsx(extra_entries=[(name, b"private")]), name),
    )
    assert any(item.code == "unsafe-xlsx-container" for item in findings)


def test_blank_scorecard_fails_closed_on_non_zip_bytes() -> None:
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"), b"not a ZIP"
    )
    assert any(item.code == "unsafe-xlsx-container" for item in findings)


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("xl/custom/private.xml", b"<private/>"),
        ("xl/custom/private.bin", b"private"),
    ],
)
def test_blank_scorecard_rejects_unrecognized_package_parts(
    name: str, data: bytes
) -> None:
    findings = validate_blank_scorecard(
        PurePosixPath("evaluation/voice-evaluation-scorecard.xlsx"),
        _xlsx(extra_entries=[(name, data)]),
    )
    assert any(item.code == "unsafe-xlsx" for item in findings)
