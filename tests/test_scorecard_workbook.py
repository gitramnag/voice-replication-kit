from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree

from tools.build_scorecard import build_scorecard


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "evaluation" / "voice-evaluation-scorecard.xlsx"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"x": MAIN_NS, "r": OFFICE_REL_NS, "p": PACKAGE_REL_NS}


@dataclass(frozen=True)
class ScorecardReport:
    sheet_names: tuple[str, ...]
    table_names: tuple[str, ...]
    freeze_panes: dict[str, str]
    populated_score_cells: tuple[str, ...]
    populated_decision_cells: tuple[str, ...]
    external_relationships: tuple[str, ...]


def _xml(archive: zipfile.ZipFile, name: str) -> ElementTree.Element:
    return ElementTree.fromstring(archive.read(name))


def _has_value(cell: ElementTree.Element) -> bool:
    value = cell.find("x:v", NS)
    inline = cell.find("x:is", NS)
    return (value is not None and bool(value.text)) or (
        inline is not None and bool("".join(inline.itertext()))
    )


def _formula(root: ElementTree.Element, reference: str) -> str:
    formula = root.find(f".//x:c[@r='{reference}']/x:f", NS)
    assert formula is not None
    return formula.text or ""


def inspect_scorecard(path: Path) -> ScorecardReport:
    with zipfile.ZipFile(path) as archive:
        workbook = _xml(archive, "xl/workbook.xml")
        sheet_names = tuple(
            item.attrib["name"] for item in workbook.findall("x:sheets/x:sheet", NS)
        )
        table_names = tuple(
            _xml(archive, name).attrib["name"]
            for name in ("xl/tables/table1.xml", "xl/tables/table2.xml")
        )
        freeze_panes: dict[str, str] = {}
        for sheet_name, part in (
            ("Ratings", "xl/worksheets/sheet2.xml"),
            ("Decisions", "xl/worksheets/sheet3.xml"),
        ):
            pane = _xml(archive, part).find("x:sheetViews/x:sheetView/x:pane", NS)
            if pane is not None:
                freeze_panes[sheet_name] = pane.attrib["topLeftCell"]

        ratings = _xml(archive, "xl/worksheets/sheet2.xml")
        populated_scores = tuple(
            cell.attrib["r"]
            for cell in ratings.findall(".//x:c", NS)
            if cell.attrib["r"][0] in "FGHIJK"
            and int(cell.attrib["r"][1:]) >= 2
            and _has_value(cell)
        )
        decisions = _xml(archive, "xl/worksheets/sheet3.xml")
        populated_decisions = tuple(
            cell.attrib["r"]
            for cell in decisions.findall(".//x:c", NS)
            if cell.attrib["r"][0] in "GH"
            and int(cell.attrib["r"][1:]) >= 2
            and _has_value(cell)
        )
        external_relationships = tuple(
            item.attrib.get("Target", "")
            for name in archive.namelist()
            if name.endswith(".rels")
            for item in _xml(archive, name).findall("p:Relationship", NS)
            if item.attrib.get("TargetMode") == "External"
        )

    return ScorecardReport(
        sheet_names,
        table_names,
        freeze_panes,
        populated_scores,
        populated_decisions,
        external_relationships,
    )


def test_scorecard_regeneration_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    build_scorecard(first)
    build_scorecard(second)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == WORKBOOK.read_bytes()


def test_scorecard_has_native_tables_validation_and_no_private_values() -> None:
    report = inspect_scorecard(WORKBOOK)

    assert report.sheet_names == ("Instructions", "Ratings", "Decisions")
    assert report.table_names == ("RatingsTable", "DecisionsTable")
    assert report.freeze_panes == {"Ratings": "A2", "Decisions": "A2"}
    assert report.populated_score_cells == ()
    assert report.populated_decision_cells == ()
    assert report.external_relationships == ()


def test_scorecard_keeps_native_validation_formulas_and_styles() -> None:
    with zipfile.ZipFile(WORKBOOK) as archive:
        ratings = _xml(archive, "xl/worksheets/sheet2.xml")
        validations = ratings.findall("x:dataValidations/x:dataValidation", NS)
        assert [item.attrib["sqref"] for item in validations] == [
            "D2:D101",
            "F2:K101",
        ]
        assert [item.attrib["type"] for item in validations] == ["list", "whole"]

        completion = ratings.find(".//x:c[@r='L2']/x:f", NS)
        mean = ratings.find(".//x:c[@r='M2']/x:f", NS)
        assert completion is not None and "COUNT(F2:K2)=6" in (completion.text or "")
        assert mean is not None and "AVERAGE(F2:K2)" in (mean.text or "")

        decisions = _xml(archive, "xl/worksheets/sheet3.xml")
        status = decisions.find(".//x:c[@r='F2']/x:f", NS)
        best = decisions.find(".//x:c[@r='D2']/x:f", NS)
        assert status is not None and "C2<B2" in (status.text or "")
        assert best is not None and "MAXIFS" in (best.text or "")

        styles = _xml(archive, "xl/styles.xml")
        style_names = {
            item.attrib["name"]
            for item in styles.findall("x:cellStyles/x:cellStyle", NS)
        }
        assert {"Normal", "Input", "Calculated", "Warning"} <= style_names
        assert any(
            item.attrib.get("formatCode") == "0.00"
            for item in styles.findall("x:numFmts/x:numFmt", NS)
        )


def test_ratings_rows_require_context_and_six_scores_before_completion() -> None:
    with zipfile.ZipFile(WORKBOOK) as archive:
        ratings = _xml(archive, "xl/worksheets/sheet2.xml")

    for row in range(2, 102):
        assert _formula(ratings, f"L{row}") == (
            f'IF(COUNTA(A{row}:K{row})=0,"",'
            f'IF(AND(COUNTA(A{row}:E{row})=5,COUNT(F{row}:K{row})=6),'
            '"Complete","Incomplete"))'
        )
        assert _formula(ratings, f"M{row}") == (
            f'IF(L{row}="Complete",AVERAGE(F{row}:K{row}),"")'
        )


def test_decision_rows_require_valid_completed_label_and_note() -> None:
    with zipfile.ZipFile(WORKBOOK) as archive:
        decisions = _xml(archive, "xl/worksheets/sheet3.xml")

    for row in range(2, 16):
        assert _formula(decisions, f"D{row}") == (
            f'IF(OR(B{row}=0,C{row}<B{row}),"",'
            f'_xlfn.MAXIFS(Ratings!$M$2:$M$101,Ratings!$D$2:$D$101,A{row},'
            'Ratings!$L$2:$L$101,"Complete"))'
        )
        assert _formula(decisions, f"F{row}") == (
            f'IF(B{row}=0,"Await candidates",IF(C{row}<B{row},"Finish ratings",'
            f'IF(G{row}="",IF(E{row}>1,"Review tie","Choose candidate"),'
            f'IF(COUNTIFS(Ratings!$A$2:$A$101,G{row},Ratings!$D$2:$D$101,A{row},'
            'Ratings!$L$2:$L$101,"Complete")=0,"Choose listed candidate",'
            f'IF(LEN(TRIM(H{row}))=0,"Add decision note","Decision recorded")))))'
        )


def test_scorecard_formulas_use_compatible_function_prefixes() -> None:
    unsupported_unprefixed = re.compile(
        r"(?<!_xlfn\.)\b(?:MAXIFS|MINIFS|XLOOKUP|UNIQUE|FILTER)\("
    )
    with zipfile.ZipFile(WORKBOOK) as archive:
        formulas = [
            formula.text or ""
            for name in (
                "xl/worksheets/sheet2.xml",
                "xl/worksheets/sheet3.xml",
            )
            for formula in _xml(archive, name).findall(".//x:f", NS)
        ]

    assert len(formulas) == 270
    assert not any(unsupported_unprefixed.search(formula) for formula in formulas)


def test_scorecard_applies_complete_row_style_and_geometry_contract() -> None:
    with zipfile.ZipFile(WORKBOOK) as archive:
        instructions = _xml(archive, "xl/worksheets/sheet1.xml")
        ratings = _xml(archive, "xl/worksheets/sheet2.xml")
        decisions = _xml(archive, "xl/worksheets/sheet3.xml")

    assert instructions.find("x:dimension", NS).attrib == {"ref": "A1:F27"}
    assert ratings.find("x:dimension", NS).attrib == {"ref": "A1:N101"}
    assert decisions.find("x:dimension", NS).attrib == {"ref": "A1:H15"}

    rating_headers = ratings.findall(".//x:row[@r='1']/x:c", NS)
    assert tuple("".join(cell.itertext()) for cell in rating_headers) == (
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
    assert {cell.attrib.get("s") for cell in rating_headers} == {"4"}
    for row in range(2, 102):
        expected_styles = {
            **{f"{column}{row}": "5" for column in "ABDE"},
            f"C{row}": "10",
            **{f"{column}{row}": "6" for column in "FGHIJK"},
            f"L{row}": "7",
            f"M{row}": "9",
            f"N{row}": "10",
        }
        observed = {
            cell.attrib["r"]: cell.attrib.get("s")
            for cell in ratings.findall(f".//x:row[@r='{row}']/x:c", NS)
        }
        assert observed == expected_styles

    decision_headers = decisions.findall(".//x:row[@r='1']/x:c", NS)
    assert tuple("".join(cell.itertext()) for cell in decision_headers) == (
        "Style",
        "Candidates started",
        "Complete candidates",
        "Best mean",
        "Tied at best",
        "Status",
        "Selected blind label",
        "Decision note",
    )
    assert {cell.attrib.get("s") for cell in decision_headers} == {"4"}
    for row in range(2, 16):
        observed = {
            cell.attrib["r"]: cell.attrib.get("s")
            for cell in decisions.findall(f".//x:row[@r='{row}']/x:c", NS)
        }
        assert observed == {
            f"A{row}": "7",
            f"B{row}": "8",
            f"C{row}": "8",
            f"D{row}": "9",
            f"E{row}": "8",
            f"F{row}": "7",
            f"G{row}": "5",
            f"H{row}": "10",
        }

    assert ratings.find(".//x:row[@r='1']", NS).attrib["ht"] == "36"
    assert ratings.find(".//x:row[@r='51']", NS).attrib["ht"] == "24"
    assert ratings.find(".//x:row[@r='101']", NS).attrib["ht"] == "24"
    assert decisions.find(".//x:row[@r='1']", NS).attrib["ht"] == "36"
    assert decisions.find(".//x:row[@r='8']", NS).attrib["ht"] == "26"
    assert decisions.find(".//x:row[@r='15']", NS).attrib["ht"] == "26"

    rating_columns = [item.attrib for item in ratings.findall("x:cols/x:col", NS)]
    assert rating_columns[2] == {
        "min": "3",
        "max": "3",
        "width": "48",
        "customWidth": "1",
    }
    conditional = ratings.find("x:conditionalFormatting", NS)
    assert conditional is not None and conditional.attrib == {"sqref": "L2:L101"}
    rule = conditional.find("x:cfRule", NS)
    assert rule is not None and rule.attrib == {
        "type": "containsText",
        "dxfId": "0",
        "priority": "1",
        "operator": "containsText",
        "text": "Incomplete",
    }


def test_scorecard_package_is_fixed_and_has_no_personal_metadata() -> None:
    with zipfile.ZipFile(WORKBOOK) as archive:
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        assert all(info.create_system == 0 for info in archive.infolist())
        assert all(info.external_attr == 0 for info in archive.infolist())
        public_xml = "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith((".xml", ".rels"))
        )

    assert "2000-01-01T00:00:00Z" in public_xml
    assert "creator" not in public_xml.casefold()
    assert "lastmodifiedby" not in public_xml.casefold()
    assert "Users\\" not in public_xml
    assert "/home/" not in public_xml


def test_worksheet_elements_follow_open_xml_schema_order() -> None:
    expected = {
        "xl/worksheets/sheet1.xml": [
            "sheetPr",
            "dimension",
            "sheetViews",
            "sheetFormatPr",
            "cols",
            "sheetData",
            "pageMargins",
        ],
        "xl/worksheets/sheet2.xml": [
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
        ],
        "xl/worksheets/sheet3.xml": [
            "sheetPr",
            "dimension",
            "sheetViews",
            "sheetFormatPr",
            "cols",
            "sheetData",
            "pageMargins",
            "tableParts",
        ],
    }

    with zipfile.ZipFile(WORKBOOK) as archive:
        observed = {
            name: [child.tag.rsplit("}", 1)[-1] for child in _xml(archive, name)]
            for name in expected
        }

    assert observed == expected
