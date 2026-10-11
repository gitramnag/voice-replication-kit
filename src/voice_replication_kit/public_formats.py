"""Fail-closed validators for the public PNG and Open XML exceptions."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path, PurePosixPath
import hashlib
import posixpath
import re
import struct
import zipfile
import zlib
from xml.etree import ElementTree


MAGIC = {
    b"RIFF": "riff-container",
    b"PK\x03\x04": "zip-container",
    b"PK\x05\x06": "zip-container",
    b"PK\x07\x08": "zip-container",
    b"\x80\x04": "python-pickle",
    b"SQLite format 3\x00": "sqlite-database",
    b"\x7fELF": "elf-binary",
    b"MZ": "windows-binary",
    b"GGUF": "gguf-model",
    b"BZh": "bzip2-archive",
    b"\x1f\x8b": "gzip-archive",
    b"7z\xbc\xaf'\x1c": "7z-archive",
    b"Rar!\x1a\x07\x00": "rar-archive",
    b"Rar!\x1a\x07\x01\x00": "rar-archive",
    b"\xfe\xed\xfa\xce": "mach-o-binary",
    b"\xce\xfa\xed\xfe": "mach-o-binary",
    b"\xfe\xed\xfa\xcf": "mach-o-binary",
    b"\xcf\xfa\xed\xfe": "mach-o-binary",
    b"\xca\xfe\xba\xbe": "mach-o-binary",
    b"\xbe\xba\xfe\xca": "mach-o-binary",
    b"\xca\xfe\xba\xbf": "mach-o-binary",
    b"\xbf\xba\xfe\xca": "mach-o-binary",
    b"\xfd7zXZ\x00": "xz-archive",
    b"\x28\xb5\x2f\xfd": "zstandard-archive",
    b"\x89PNG\r\n\x1a\n": "png-image",
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": "compound-binary",
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_CHUNKS = {
    b"IHDR",
    b"PLTE",
    b"IDAT",
    b"IEND",
    b"tRNS",
    b"sRGB",
    b"gAMA",
    b"cHRM",
    b"pHYs",
}
MAX_ZIP_ENTRIES = 256
MAX_ZIP_ENTRY_BYTES = 20 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 50 * 1024 * 1024
MAX_ZIP_RATIO = 100

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REFERENCE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
_EXPECTED_SHEETS = (
    ("Instructions", "1", "xl/worksheets/sheet1.xml"),
    ("Ratings", "2", "xl/worksheets/sheet2.xml"),
    ("Decisions", "3", "xl/worksheets/sheet3.xml"),
)
_EXPECTED_PANES = {
    "xl/worksheets/sheet1.xml": None,
    "xl/worksheets/sheet2.xml": {
        "ySplit": "1",
        "topLeftCell": "A2",
        "activePane": "bottomLeft",
        "state": "frozen",
    },
    "xl/worksheets/sheet3.xml": {
        "ySplit": "1",
        "topLeftCell": "A2",
        "activePane": "bottomLeft",
        "state": "frozen",
    },
}
_EXPECTED_TABLES = {
    "xl/worksheets/sheet2.xml": (
        "xl/tables/table1.xml",
        "RatingsTable",
        "A1:N101",
        "14",
    ),
    "xl/worksheets/sheet3.xml": (
        "xl/tables/table2.xml",
        "DecisionsTable",
        "A1:H15",
        "8",
    ),
}
_EXPECTED_RELATIONSHIPS = {
    "_rels/.rels": frozenset(
        {
            (
                "rId1",
                f"{_OFFICE_REL_NS}/officeDocument",
                "/xl/workbook.xml",
            ),
            (
                "rId2",
                "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
                "/docProps/core.xml",
            ),
        }
    ),
    "xl/_rels/workbook.xml.rels": frozenset(
        {
            (
                "rId1",
                f"{_OFFICE_REL_NS}/styles",
                "/xl/styles.xml",
            ),
            (
                "rId3",
                f"{_OFFICE_REL_NS}/worksheet",
                "/xl/worksheets/sheet1.xml",
            ),
            (
                "rId4",
                f"{_OFFICE_REL_NS}/worksheet",
                "/xl/worksheets/sheet2.xml",
            ),
            (
                "rId5",
                f"{_OFFICE_REL_NS}/worksheet",
                "/xl/worksheets/sheet3.xml",
            ),
        }
    ),
    "xl/worksheets/_rels/sheet2.xml.rels": frozenset(
        {
            (
                "rId1",
                f"{_OFFICE_REL_NS}/table",
                "/xl/tables/table1.xml",
            )
        }
    ),
    "xl/worksheets/_rels/sheet3.xml.rels": frozenset(
        {
            (
                "rId1",
                f"{_OFFICE_REL_NS}/table",
                "/xl/tables/table2.xml",
            )
        }
    ),
}
_STYLE_VALIDATION = (
    '"narration_neutral,warm_friendly,excited_energetic,serious_authoritative,'
    "curious_questioning,empathetic_calm,emphatic_punchy,awe_wonder,sorrow_grief,"
    "anger_fierce,tender_intimate,suspense_hushed,playful_wry,"
    'triumphant_declaratory"'
)
_EXPECTED_XLSX_PARTS = frozenset(
    {
        "[content_types].xml",
        "_rels/.rels",
        "docprops/core.xml",
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
        "xl/styles.xml",
        "xl/worksheets/sheet1.xml",
        "xl/worksheets/sheet2.xml",
        "xl/worksheets/_rels/sheet2.xml.rels",
        "xl/tables/table1.xml",
        "xl/worksheets/sheet3.xml",
        "xl/worksheets/_rels/sheet3.xml.rels",
        "xl/tables/table2.xml",
    }
)

_STYLES_XML_SHA256 = "408e588ed4d986543867b79b769827f0d2bcb3359b5b4e9ca2ea363349542b14"
_INSTRUCTIONS_XML_SHA256 = "ee86aab5045c65d1a46c075d6814ca2da12f37913dfbba97d40dad18f5ad947a"
_STYLES = (
    "narration_neutral",
    "warm_friendly",
    "excited_energetic",
    "serious_authoritative",
    "curious_questioning",
    "empathetic_calm",
    "emphatic_punchy",
    "awe_wonder",
    "sorrow_grief",
    "anger_fierce",
    "tender_intimate",
    "suspense_hushed",
    "playful_wry",
    "triumphant_declaratory",
)
_RATING_HEADERS = (
    "Blind label",
    "Prompt ID",
    "Prompt text",
    "Style",
    "Candidate file",
    "Identity",
    "Naturalness",
    "Pacing",
    "Pronunciation",
    "Artifact-free",
    "Emotion fit",
    "Ratings complete",
    "Mean score",
    "Notes",
)
_DECISION_HEADERS = (
    "Style",
    "Candidates started",
    "Complete candidates",
    "Best mean",
    "Tied at best",
    "Status",
    "Selected blind label",
    "Decision note",
)
_EXPECTED_DIMENSIONS = {
    "xl/worksheets/sheet1.xml": "A1:F27",
    "xl/worksheets/sheet2.xml": "A1:N101",
    "xl/worksheets/sheet3.xml": "A1:H15",
}
_EXPECTED_COLUMNS = {
    "xl/worksheets/sheet2.xml": (
        ("1", "1", "15"),
        ("2", "2", "18"),
        ("3", "3", "48"),
        ("4", "4", "25"),
        ("5", "5", "26"),
        ("6", "11", "14"),
        ("12", "12", "18"),
        ("13", "13", "13"),
        ("14", "14", "36"),
    ),
    "xl/worksheets/sheet3.xml": (
        ("1", "1", "27"),
        ("2", "3", "20"),
        ("4", "5", "13"),
        ("6", "6", "20"),
        ("7", "7", "22"),
        ("8", "8", "44"),
    ),
}
_EXPECTED_WORKSHEET_CHILDREN = {
    "xl/worksheets/sheet1.xml": (
        "sheetPr",
        "dimension",
        "sheetViews",
        "sheetFormatPr",
        "cols",
        "sheetData",
        "pageMargins",
    ),
    "xl/worksheets/sheet2.xml": (
        "sheetPr",
        "dimension",
        "sheetViews",
        "sheetFormatPr",
        "cols",
        "sheetData",
        "conditionalFormatting",
        "dataValidations",
        "pageMargins",
        "tableParts",
    ),
    "xl/worksheets/sheet3.xml": (
        "sheetPr",
        "dimension",
        "sheetViews",
        "sheetFormatPr",
        "cols",
        "sheetData",
        "pageMargins",
        "tableParts",
    ),
}


def _finding(code: str, path: PurePosixPath, detail: str):
    from voice_replication_kit.privacy import Finding

    return Finding(code, Path(*path.parts), detail)


def detect_signature(data: bytes) -> str | None:
    """Return a known binary signature without trusting the filename."""
    detected = next(
        (name for prefix, name in MAGIC.items() if data.startswith(prefix)), None
    )
    if detected is not None:
        return detected
    if data[257:263] == b"ustar\x00" or data[257:263] == b"ustar ":
        return "tar-archive"
    return None


class _InvalidPng(ValueError):
    pass


_PNG_SINGLETON_CHUNKS = {b"PLTE", b"sRGB", b"gAMA", b"cHRM", b"pHYs", b"tRNS"}
_SRGB_CHROMATICITIES = (
    31270,
    32900,
    64000,
    33000,
    30000,
    60000,
    15000,
    6000,
)


def _png_passes(width: int, height: int, interlace: int) -> list[tuple[int, int]]:
    if interlace == 0:
        return [(width, height)]
    passes = (
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    )
    result = []
    for x_start, y_start, x_step, y_step in passes:
        pass_width = 0 if width <= x_start else (width - x_start + x_step - 1) // x_step
        pass_height = 0 if height <= y_start else (height - y_start + y_step - 1) // y_step
        if pass_width and pass_height:
            result.append((pass_width, pass_height))
    return result


def _validate_png_ancillary(
    chunks: list[tuple[bytes, bytes]],
    kinds: list[bytes],
    *,
    bit_depth: int,
    color_type: int,
    first_idat: int,
) -> None:
    for kind in _PNG_SINGLETON_CHUNKS:
        if kinds.count(kind) > 1:
            raise _InvalidPng("duplicate ancillary chunk")
        if kind in kinds and kinds.index(kind) > first_idat:
            raise _InvalidPng("ancillary chunk order")

    palette_index = kinds.index(b"PLTE") if b"PLTE" in kinds else None
    for kind in (b"sRGB", b"gAMA", b"cHRM"):
        if (
            kind in kinds
            and palette_index is not None
            and kinds.index(kind) > palette_index
        ):
            raise _InvalidPng("color chunk order")

    payloads = {
        kind: payload
        for kind, payload in chunks
        if kind in _PNG_SINGLETON_CHUNKS
    }
    if b"sRGB" in payloads:
        if len(payloads[b"sRGB"]) != 1 or payloads[b"sRGB"][0] > 3:
            raise _InvalidPng("sRGB")
    if b"gAMA" in payloads:
        if len(payloads[b"gAMA"]) != 4:
            raise _InvalidPng("gAMA length")
        gamma = struct.unpack(">I", payloads[b"gAMA"])[0]
        if gamma == 0 or (b"sRGB" in payloads and gamma != 45455):
            raise _InvalidPng("gAMA value")
    if b"cHRM" in payloads:
        if len(payloads[b"cHRM"]) != 32:
            raise _InvalidPng("cHRM length")
        chromaticities = struct.unpack(">8I", payloads[b"cHRM"])
        pairs = zip(chromaticities[::2], chromaticities[1::2])
        if any(
            x == 0 or y == 0 or x > 100000 or y > 100000 or x + y > 100000
            for x, y in pairs
        ):
            raise _InvalidPng("cHRM value")
        if b"sRGB" in payloads and chromaticities != _SRGB_CHROMATICITIES:
            raise _InvalidPng("cHRM sRGB mismatch")
    if b"pHYs" in payloads:
        if len(payloads[b"pHYs"]) != 9:
            raise _InvalidPng("pHYs length")
        pixels_x, pixels_y, unit = struct.unpack(">IIB", payloads[b"pHYs"])
        if pixels_x == 0 or pixels_y == 0 or unit not in {0, 1}:
            raise _InvalidPng("pHYs value")
    if b"tRNS" in payloads:
        transparency = payloads[b"tRNS"]
        if color_type == 0:
            if (
                len(transparency) != 2
                or struct.unpack(">H", transparency)[0] >= 2**bit_depth
            ):
                raise _InvalidPng("tRNS grayscale")
        elif color_type == 2:
            if len(transparency) != 6 or any(
                sample >= 2**bit_depth for sample in struct.unpack(">3H", transparency)
            ):
                raise _InvalidPng("tRNS truecolor")
        elif color_type == 3:
            if palette_index is None or kinds.index(b"tRNS") < palette_index:
                raise _InvalidPng("tRNS palette order")
            palette_entries = len(payloads[b"PLTE"]) // 3
            if not transparency or len(transparency) > palette_entries:
                raise _InvalidPng("tRNS palette")
        else:
            raise _InvalidPng("tRNS with alpha")


def _validate_png_bytes(data: bytes) -> None:
    if not data.startswith(PNG_SIGNATURE):
        raise _InvalidPng("signature")
    offset = len(PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(data):
        if len(data) - offset < 12:
            raise _InvalidPng("truncated chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(data):
            raise _InvalidPng("truncated payload")
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        checksum = struct.unpack(">I", data[offset + 8 + length : end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != checksum:
            raise _InvalidPng("checksum")
        if kind not in PNG_CHUNKS:
            raise PermissionError("disallowed chunk")
        chunks.append((kind, payload))
        offset = end
        if kind == b"IEND":
            break
    if offset != len(data):
        raise _InvalidPng("trailing bytes")
    kinds = [kind for kind, _payload in chunks]
    if not kinds or kinds[0] != b"IHDR" or kinds[-1] != b"IEND":
        raise _InvalidPng("chunk order")
    if kinds.count(b"IHDR") != 1 or kinds.count(b"IEND") != 1:
        raise _InvalidPng("duplicate framing chunk")
    if b"IDAT" not in kinds:
        raise _InvalidPng("missing image data")
    first_idat = kinds.index(b"IDAT")
    last_idat = len(kinds) - 1 - kinds[::-1].index(b"IDAT")
    if any(kind != b"IDAT" for kind in kinds[first_idat : last_idat + 1]):
        raise _InvalidPng("split image data")

    ihdr = chunks[0][1]
    if len(ihdr) != 13:
        raise _InvalidPng("header length")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    valid_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if (
        not width
        or not height
        or color_type not in valid_depths
        or bit_depth not in valid_depths[color_type]
        or compression != 0
        or filtering != 0
        or interlace not in {0, 1}
    ):
        raise _InvalidPng("header values")
    if color_type == 3 and b"PLTE" not in kinds:
        raise _InvalidPng("missing palette")
    if b"PLTE" in kinds:
        palette = chunks[kinds.index(b"PLTE")][1]
        if color_type in {0, 4} or not palette or len(palette) % 3 or len(palette) > 768:
            raise _InvalidPng("palette")
        if color_type == 3 and len(palette) // 3 > 2**bit_depth:
            raise _InvalidPng("palette exceeds indexed bit depth")
        if kinds.index(b"PLTE") > first_idat:
            raise _InvalidPng("palette order")
    _validate_png_ancillary(
        chunks,
        kinds,
        bit_depth=bit_depth,
        color_type=color_type,
        first_idat=first_idat,
    )

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    bits_per_pixel = channels * bit_depth
    passes = _png_passes(width, height, interlace)
    expected = sum(
        ((pass_width * bits_per_pixel + 7) // 8 + 1) * pass_height
        for pass_width, pass_height in passes
    )
    if expected > 200 * 1024 * 1024:
        raise _InvalidPng("decoded size")
    compressed = b"".join(payload for kind, payload in chunks if kind == b"IDAT")
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(compressed, expected + 1)
        decoded += inflater.flush(expected + 1 - len(decoded))
    except zlib.error as error:
        raise _InvalidPng("compressed image data") from error
    if len(decoded) != expected or not inflater.eof or inflater.unused_data:
        raise _InvalidPng("decoded image data")
    offset = 0
    for pass_width, pass_height in passes:
        stride = (pass_width * bits_per_pixel + 7) // 8 + 1
        for _row in range(pass_height):
            if decoded[offset] > 4:
                raise _InvalidPng("filter")
            offset += stride


def validate_public_png(path: PurePosixPath, data: bytes) -> list:
    """Accept only a structurally valid PNG with no metadata-bearing chunks."""
    try:
        _validate_png_bytes(data)
    except PermissionError:
        return [_finding("unsafe-png", path, "PNG contains a disallowed metadata chunk")]
    except (ValueError, struct.error, OverflowError):
        return [_finding("malformed-png", path, "PNG structure is malformed")]
    return []


class _UnsafeContainer(ValueError):
    pass


def _safe_zip(data: bytes) -> tuple[zipfile.ZipFile, dict[str, zipfile.ZipInfo]]:
    try:
        archive = zipfile.ZipFile(BytesIO(data))
        infos = archive.infolist()
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        raise _UnsafeContainer("invalid ZIP") from error
    if not infos or len(infos) > MAX_ZIP_ENTRIES:
        archive.close()
        raise _UnsafeContainer("entry count")
    names: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        lowered = name.casefold()
        parts = PurePosixPath(name).parts
        if (
            not name
            or name.startswith("/")
            or re.match(r"^[A-Za-z]:", name)
            or any(part in {"", ".", ".."} for part in parts)
            or lowered in names
            or info.flag_bits & 1
            or info.file_size > MAX_ZIP_ENTRY_BYTES
            or (info.file_size and info.file_size / max(info.compress_size, 1) > MAX_ZIP_RATIO)
        ):
            archive.close()
            raise _UnsafeContainer("unsafe entry")
        total += info.file_size
        if total > MAX_ZIP_TOTAL_BYTES:
            archive.close()
            raise _UnsafeContainer("total size")
        names[lowered] = info
    return archive, names


def _xml(data: bytes) -> ElementTree.Element:
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise _UnsafeContainer("active XML declaration")
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise _UnsafeContainer("malformed XML") from error


def _read(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        return archive.read(name)
    except (KeyError, RuntimeError, zipfile.BadZipFile, zlib.error) as error:
        raise _UnsafeContainer("unreadable entry") from error


def _relationship_target(base: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(base, target))


def _column_number(cell_reference: str) -> tuple[int, int] | None:
    match = _CELL_REFERENCE.fullmatch(cell_reference.upper())
    if not match:
        return None
    column = 0
    for character in match.group(1):
        column = column * 26 + ord(character) - ord("A") + 1
    return column, int(match.group(2))


def _cell_has_value(cell: ElementTree.Element) -> bool:
    value = cell.find(f"{{{_MAIN_NS}}}v")
    if value is not None and (value.text or "") != "":
        return True
    inline = cell.find(f"{{{_MAIN_NS}}}is")
    return inline is not None and "".join(inline.itertext()) != ""


def _relationship_map(root: ElementTree.Element) -> dict[str, ElementTree.Element]:
    relationships = root.findall(f".//{{{_PACKAGE_REL_NS}}}Relationship")
    identifiers = [item.attrib.get("Id", "") for item in relationships]
    if any(not identifier for identifier in identifiers) or len(identifiers) != len(
        set(identifiers)
    ):
        raise _UnsafeContainer("duplicate relationship")
    return dict(zip(identifiers, relationships))


def _relationship_inventory_is_expected(
    parsed: dict[str, ElementTree.Element],
) -> bool:
    relationship_parts = {
        name for name in parsed if name.endswith(".rels")
    }
    if relationship_parts != set(_EXPECTED_RELATIONSHIPS):
        return False
    for name, expected in _EXPECTED_RELATIONSHIPS.items():
        relationships = _relationship_map(parsed[name]).values()
        if any(set(item.attrib) != {"Id", "Type", "Target"} for item in relationships):
            return False
        observed = frozenset(
            (
                item.attrib["Id"],
                item.attrib["Type"],
                item.attrib["Target"],
            )
            for item in relationships
        )
        if observed != expected:
            return False
    return True


def _worksheet_relationship_path(sheet_path: str) -> str:
    directory, filename = sheet_path.rsplit("/", 1)
    return f"{directory}/_rels/{filename}.rels"


def _xml_sha256(root: ElementTree.Element) -> str:
    return hashlib.sha256(ElementTree.tostring(root, encoding="utf-8")).hexdigest()


def _worksheet_cells(root: ElementTree.Element) -> dict[str, ElementTree.Element] | None:
    cells = root.findall(f".//{{{_MAIN_NS}}}c")
    references = [cell.attrib.get("r", "") for cell in cells]
    if any(not reference for reference in references) or len(references) != len(
        set(references)
    ):
        return None
    return dict(zip(references, cells))


def _cell_is_blank(cell: ElementTree.Element, reference: str, style: str) -> bool:
    return cell.attrib == {"r": reference, "s": style} and len(cell) == 0


def _cell_has_formula(
    cell: ElementTree.Element, reference: str, style: str, formula: str
) -> bool:
    return (
        cell.attrib == {"r": reference, "s": style}
        and len(cell) == 1
        and cell[0].tag == f"{{{_MAIN_NS}}}f"
        and (cell[0].text or "") == formula
        and not cell[0].attrib
    )


def _cell_has_text(
    cell: ElementTree.Element, reference: str, style: str, text: str
) -> bool:
    return (
        cell.attrib == {"r": reference, "s": style, "t": "inlineStr"}
        and "".join(cell.itertext()) == text
    )


def _rows_are_exact(
    root: ElementTree.Element, first: int, last: int, heights: dict[int, str]
) -> bool:
    rows = root.findall(f"{{{_MAIN_NS}}}sheetData/{{{_MAIN_NS}}}row")
    if [row.attrib.get("r") for row in rows] != [str(row) for row in range(first, last + 1)]:
        return False
    return all(
        row.attrib
        == {
            "r": str(number),
            "ht": heights[number],
            "customHeight": "1",
        }
        for number, row in zip(range(first, last + 1), rows)
    )


def _worksheet_contract_is_expected(
    sheet_path: str, root: ElementTree.Element
) -> bool:
    if tuple(child.tag.rsplit("}", 1)[-1] for child in root) != _EXPECTED_WORKSHEET_CHILDREN[
        sheet_path
    ]:
        return False
    dimension = root.find(f"{{{_MAIN_NS}}}dimension")
    if dimension is None or dimension.attrib != {"ref": _EXPECTED_DIMENSIONS[sheet_path]}:
        return False
    if sheet_path == "xl/worksheets/sheet1.xml":
        return _xml_sha256(root) == _INSTRUCTIONS_XML_SHA256

    expected_columns = _EXPECTED_COLUMNS[sheet_path]
    columns = root.findall(f"{{{_MAIN_NS}}}cols/{{{_MAIN_NS}}}col")
    if tuple(
        (
            column.attrib.get("min"),
            column.attrib.get("max"),
            column.attrib.get("width"),
        )
        for column in columns
    ) != expected_columns or any(
        set(column.attrib) != {"min", "max", "width", "customWidth"}
        or column.attrib.get("customWidth") != "1"
        for column in columns
    ):
        return False

    cells = _worksheet_cells(root)
    if cells is None:
        return False
    if sheet_path == "xl/worksheets/sheet2.xml":
        if not _rows_are_exact(
            root, 1, 101, {1: "36", **{row: "24" for row in range(2, 102)}}
        ):
            return False
        expected_references = {
            f"{column}{row}"
            for row in range(1, 102)
            for column in "ABCDEFGHIJKLMN"
        }
        if set(cells) != expected_references:
            return False
        for index, header in enumerate(_RATING_HEADERS):
            reference = f"{chr(65 + index)}1"
            if not _cell_has_text(cells[reference], reference, "4", header):
                return False
        for row in range(2, 102):
            blank_styles = {
                **{column: "5" for column in "ABDE"},
                "C": "10",
                **{column: "6" for column in "FGHIJK"},
                "N": "10",
            }
            if any(
                not _cell_is_blank(cells[f"{column}{row}"], f"{column}{row}", style)
                for column, style in blank_styles.items()
            ):
                return False
            completion = (
                f'IF(COUNTA(A{row}:K{row})=0,"",'
                f'IF(AND(COUNTA(A{row}:E{row})=5,COUNT(F{row}:K{row})=6),'
                '"Complete","Incomplete"))'
            )
            mean = f'IF(L{row}="Complete",AVERAGE(F{row}:K{row}),"")'
            if not _cell_has_formula(cells[f"L{row}"], f"L{row}", "7", completion):
                return False
            if not _cell_has_formula(cells[f"M{row}"], f"M{row}", "9", mean):
                return False
        conditional = root.find(f"{{{_MAIN_NS}}}conditionalFormatting")
        if conditional is None or conditional.attrib != {"sqref": "L2:L101"}:
            return False
        rules = list(conditional)
        return (
            len(rules) == 1
            and rules[0].tag == f"{{{_MAIN_NS}}}cfRule"
            and rules[0].attrib
            == {
                "type": "containsText",
                "dxfId": "0",
                "priority": "1",
                "operator": "containsText",
                "text": "Incomplete",
            }
            and len(rules[0]) == 1
            and rules[0][0].tag == f"{{{_MAIN_NS}}}formula"
            and (rules[0][0].text or "")
            == 'NOT(ISERROR(SEARCH("Incomplete",L2)))'
        )

    if not _rows_are_exact(
        root, 1, 15, {1: "36", **{row: "26" for row in range(2, 16)}}
    ):
        return False
    expected_references = {
        f"{column}{row}" for row in range(1, 16) for column in "ABCDEFGH"
    }
    if set(cells) != expected_references:
        return False
    for index, header in enumerate(_DECISION_HEADERS):
        reference = f"{chr(65 + index)}1"
        if not _cell_has_text(cells[reference], reference, "4", header):
            return False
    for row, style_name in enumerate(_STYLES, start=2):
        if not _cell_has_text(cells[f"A{row}"], f"A{row}", "7", style_name):
            return False
        formulas = {
            "B": (
                "8",
                f'COUNTIFS(Ratings!$D$2:$D$101,A{row},Ratings!$A$2:$A$101,"<>")',
            ),
            "C": (
                "8",
                f'COUNTIFS(Ratings!$D$2:$D$101,A{row},Ratings!$L$2:$L$101,"Complete")',
            ),
            "D": (
                "9",
                f'IF(OR(B{row}=0,C{row}<B{row}),"",_xlfn.MAXIFS('
                f'Ratings!$M$2:$M$101,Ratings!$D$2:$D$101,A{row},'
                'Ratings!$L$2:$L$101,"Complete"))',
            ),
            "E": (
                "8",
                f'IF(D{row}="","",COUNTIFS(Ratings!$D$2:$D$101,A{row},'
                'Ratings!$L$2:$L$101,"Complete",Ratings!$M$2:$M$101,'
                f'D{row}))',
            ),
            "F": (
                "7",
                f'IF(B{row}=0,"Await candidates",IF(C{row}<B{row},"Finish ratings",'
                f'IF(G{row}="",IF(E{row}>1,"Review tie","Choose candidate"),'
                f'IF(COUNTIFS(Ratings!$A$2:$A$101,G{row},'
                f'Ratings!$D$2:$D$101,A{row},Ratings!$L$2:$L$101,"Complete")=0,'
                f'"Choose listed candidate",IF(LEN(TRIM(H{row}))=0,'
                '"Add decision note","Decision recorded")))))',
            ),
        }
        if any(
            not _cell_has_formula(cells[f"{column}{row}"], f"{column}{row}", style, formula)
            for column, (style, formula) in formulas.items()
        ):
            return False
        if not _cell_is_blank(cells[f"G{row}"], f"G{row}", "5") or not _cell_is_blank(
            cells[f"H{row}"], f"H{row}", "10"
        ):
            return False
    return True


def _worksheet_structure_is_expected(
    sheet_path: str,
    root: ElementTree.Element,
    parsed: dict[str, ElementTree.Element],
) -> bool:
    panes = root.findall(f".//{{{_MAIN_NS}}}pane")
    expected_pane = _EXPECTED_PANES[sheet_path]
    if expected_pane is None:
        if panes:
            return False
    elif len(panes) != 1 or panes[0].attrib != expected_pane:
        return False

    validations = root.findall(f".//{{{_MAIN_NS}}}dataValidation")
    validation_parent = root.find(f".//{{{_MAIN_NS}}}dataValidations")
    if sheet_path == "xl/worksheets/sheet2.xml":
        if validation_parent is None or validation_parent.attrib.get("count") != "2":
            return False
        observed = []
        for item in validations:
            observed.append(
                (
                    item.attrib,
                    tuple(
                        (child.tag.rsplit("}", 1)[-1], child.text or "")
                        for child in item
                    ),
                )
            )
        expected = [
            (
                {
                    "type": "list",
                    "allowBlank": "1",
                    "showErrorMessage": "1",
                    "sqref": "D2:D101",
                },
                (("formula1", _STYLE_VALIDATION),),
            ),
            (
                {
                    "type": "whole",
                    "operator": "between",
                    "allowBlank": "1",
                    "showErrorMessage": "1",
                    "errorStyle": "stop",
                    "errorTitle": "Invalid rating",
                    "error": "Rating must be a whole number from 1 to 5.",
                    "sqref": "F2:K101",
                },
                (("formula1", "1"), ("formula2", "5")),
            ),
        ]
        if observed != expected:
            return False
    elif validations or validation_parent is not None:
        return False

    table_parts = root.findall(f".//{{{_MAIN_NS}}}tablePart")
    table_parent = root.find(f".//{{{_MAIN_NS}}}tableParts")
    expected_table = _EXPECTED_TABLES.get(sheet_path)
    if expected_table is None:
        return not table_parts and table_parent is None
    if (
        table_parent is None
        or table_parent.attrib.get("count") != "1"
        or len(table_parts) != 1
    ):
        return False
    relationship_id = table_parts[0].attrib.get(f"{{{_OFFICE_REL_NS}}}id", "")
    relationships = parsed.get(_worksheet_relationship_path(sheet_path))
    if relationships is None:
        return False
    relationship = _relationship_map(relationships).get(relationship_id)
    if relationship is None:
        return False
    table_path, table_name, table_ref, column_count = expected_table
    if (
        relationship.attrib.get("Type", "").rsplit("/", 1)[-1] != "table"
        or _relationship_target(
            "xl/worksheets", relationship.attrib.get("Target", "")
        ).casefold()
        != table_path
    ):
        return False
    table = parsed.get(table_path)
    if table is None:
        return False
    columns = table.find(f"{{{_MAIN_NS}}}tableColumns")
    auto_filter = table.find(f"{{{_MAIN_NS}}}autoFilter")
    expected_headers = (
        _RATING_HEADERS if table_name == "RatingsTable" else _DECISION_HEADERS
    )
    table_columns = [] if columns is None else columns.findall(
        f"{{{_MAIN_NS}}}tableColumn"
    )
    table_style = table.find(f"{{{_MAIN_NS}}}tableStyleInfo")
    return (
        table.attrib
        == {
            "id": "1" if table_name == "RatingsTable" else "2",
            "name": table_name,
            "displayName": table_name,
            "ref": table_ref,
            "headerRowCount": "1",
            "totalsRowCount": "0",
            "totalsRowShown": "0",
        }
        and auto_filter is not None
        and auto_filter.attrib == {"ref": table_ref}
        and columns is not None
        and columns.attrib == {"count": column_count}
        and [item.attrib for item in table_columns]
        == [
            {"id": str(index), "name": header}
            for index, header in enumerate(expected_headers, start=1)
        ]
        and table_style is not None
        and table_style.attrib
        == {
            "name": "VoiceScorecard",
            "showFirstColumn": "0",
            "showLastColumn": "0",
            "showRowStripes": "1",
            "showColumnStripes": "0",
        }
    )


def decoded_scorecard_text(data: bytes) -> str:
    """Return canonical decoded XML text after the ZIP preflight succeeds."""
    archive, names = _safe_zip(data)
    try:
        roots = [
            _xml(_read(archive, info.filename))
            for name, info in names.items()
            if name.endswith((".xml", ".rels"))
        ]
    finally:
        archive.close()
    return "\n".join(
        ElementTree.tostring(root, encoding="unicode") for root in roots
    )


def validate_blank_scorecard(path: PurePosixPath, data: bytes) -> list:
    """Validate ZIP safety, Open XML relationships, metadata, and blank inputs."""
    try:
        archive, names = _safe_zip(data)
    except _UnsafeContainer:
        return [_finding("unsafe-xlsx-container", path, "Open XML container is unsafe")]
    try:
        if set(names) != _EXPECTED_XLSX_PARTS:
            return [
                _finding(
                    "unsafe-xlsx",
                    path,
                    "scorecard package inventory drifted",
                )
            ]
        disallowed_prefixes = (
            "xl/comments",
            "xl/externallinks",
            "xl/media",
            "xl/embeddings",
        )
        if any(name.startswith(disallowed_prefixes) for name in names):
            return [_finding("unsafe-xlsx", path, "scorecard contains private package parts")]

        parsed: dict[str, ElementTree.Element] = {}
        for lowered, info in names.items():
            if lowered.endswith((".xml", ".rels")):
                parsed[lowered] = _xml(_read(archive, info.filename))

        for lowered, root in parsed.items():
            if not lowered.endswith(".rels"):
                continue
            for relationship in root.findall(f".//{{{_PACKAGE_REL_NS}}}Relationship"):
                target = relationship.attrib.get("Target", "")
                if (
                    relationship.attrib.get("TargetMode", "").casefold() == "external"
                    or re.match(r"(?i)^(?:https?|file):", target)
                    or target.startswith("//")
                ):
                    return [_finding("unsafe-xlsx", path, "scorecard has an external relationship")]
        core = parsed.get("docprops/core.xml")
        if core is not None:
            private_names = {"creator", "lastModifiedBy"}
            if any(
                element.tag.rsplit("}", 1)[-1] in private_names
                and "".join(element.itertext()).strip()
                for element in core.iter()
            ):
                return [_finding("unsafe-xlsx", path, "scorecard contains personal package metadata")]
        if "docprops/custom.xml" in names:
            return [_finding("unsafe-xlsx", path, "scorecard contains custom package metadata")]

        workbook = parsed["xl/workbook.xml"]
        relationships = parsed["xl/_rels/workbook.xml.rels"]
        relationship_by_id = _relationship_map(relationships)
        sheets: list[tuple[str, str, str]] = []
        for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
            if sheet.attrib.get("state", "visible").casefold() != "visible":
                return [_finding("unsafe-xlsx", path, "scorecard contains a hidden sheet")]
            relationship_id = sheet.attrib.get(f"{{{_OFFICE_REL_NS}}}id", "")
            relationship = relationship_by_id.get(relationship_id)
            if relationship is None:
                return [
                    _finding(
                        "unsafe-xlsx",
                        path,
                        "scorecard worksheet relationship is missing",
                    )
                ]
            target = relationship.attrib.get("Target", "")
            normalized = _relationship_target("xl", target).casefold()
            if (
                relationship.attrib.get("Type", "").rsplit("/", 1)[-1]
                != "worksheet"
                or not target
                or normalized not in names
            ):
                return [
                    _finding(
                        "unsafe-xlsx",
                        path,
                        "scorecard worksheet relationship drifted",
                    )
                ]
            sheets.append(
                (
                    sheet.attrib.get("name", ""),
                    sheet.attrib.get("sheetId", ""),
                    normalized,
                )
            )

        for _sheet_name, _sheet_id, sheet_path in sheets:
            root = parsed.get(sheet_path)
            if root is None:
                raise _UnsafeContainer("worksheet is not XML")
            hidden_rows = root.findall(f".//{{{_MAIN_NS}}}row")
            hidden_columns = root.findall(f".//{{{_MAIN_NS}}}col")
            if any(
                element.attrib.get("hidden", "0") not in {"0", "false", "False"}
                for element in hidden_rows + hidden_columns
            ):
                return [_finding("unsafe-xlsx", path, "scorecard contains hidden rows or columns")]
            for cell in root.findall(f".//{{{_MAIN_NS}}}c"):
                formula = cell.find(f"{{{_MAIN_NS}}}f")
                if formula is not None and _cell_has_value(cell):
                    return [_finding("cached-formula-result", path, "scorecard contains cached formula results")]
                reference = _column_number(cell.attrib.get("r", ""))
                if reference is None:
                    raise _UnsafeContainer("invalid cell reference")
                column, row = reference
                blank_input = (
                    sheet_path == "xl/worksheets/sheet2.xml"
                    and row >= 2
                    and (1 <= column <= 11 or column == 14)
                ) or (
                    sheet_path == "xl/worksheets/sheet3.xml"
                    and row >= 2
                    and 7 <= column <= 8
                )
                if blank_input and (formula is not None or _cell_has_value(cell)):
                    return [_finding("populated-scorecard", path, "scorecard input cells are not blank")]
        if _xml_sha256(parsed["xl/styles.xml"]) != _STYLES_XML_SHA256:
            return [
                _finding("unsafe-xlsx", path, "scorecard style definitions drifted")
            ]
        if not _relationship_inventory_is_expected(parsed):
            return [
                _finding(
                    "unsafe-xlsx",
                    path,
                    "scorecard relationship inventory drifted",
                )
            ]
        if tuple(sheets) != _EXPECTED_SHEETS:
            return [
                _finding(
                    "unsafe-xlsx", path, "scorecard worksheet inventory drifted"
                )
            ]
        if any(
            not _worksheet_contract_is_expected(sheet_path, parsed[sheet_path])
            or not _worksheet_structure_is_expected(
                sheet_path, parsed[sheet_path], parsed
            )
            for _name, _sheet_id, sheet_path in sheets
        ):
            return [
                _finding("unsafe-xlsx", path, "scorecard native structures drifted")
            ]
    except _UnsafeContainer:
        return [_finding("unsafe-xlsx-container", path, "Open XML container is unsafe")]
    finally:
        archive.close()
    return []
