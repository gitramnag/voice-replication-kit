"""Build the public voice-evaluation scorecard as deterministic Open XML."""

from __future__ import annotations

import argparse
from html import escape
from io import BytesIO
from pathlib import Path
import struct
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation" / "voice-evaluation-scorecard.xlsx"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

STYLES = (
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

RATING_HEADERS = (
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

DECISION_HEADERS = (
    "Style",
    "Candidates started",
    "Complete candidates",
    "Best mean",
    "Tied at best",
    "Status",
    "Selected blind label",
    "Decision note",
)


def _xml(text: str) -> bytes:
    return f"{XML_HEADER}{text}".encode("utf-8")


def _attr(value: object) -> str:
    return escape(str(value), quote=True)


def _text_cell(reference: str, value: str, style: int) -> str:
    return (
        f'<c r="{reference}" s="{style}" t="inlineStr">'
        f"<is><t>{escape(value)}</t></is></c>"
    )


def _number_cell(reference: str, value: int, style: int) -> str:
    return f'<c r="{reference}" s="{style}"><v>{value}</v></c>'


def _blank_cell(reference: str, style: int) -> str:
    return f'<c r="{reference}" s="{style}"/>'


def _formula_cell(reference: str, formula: str, style: int) -> str:
    return f'<c r="{reference}" s="{style}"><f>{escape(formula)}</f></c>'


def _row(number: int, cells: list[str], height: int | None = None) -> str:
    height_attributes = "" if height is None else f' ht="{height}" customHeight="1"'
    return f'<row r="{number}"{height_attributes}>{"".join(cells)}</row>'


def _relationships(items: tuple[tuple[str, str, str], ...]) -> bytes:
    children = "".join(
        f'<Relationship Id="{identifier}" Type="{relationship_type}" '
        f'Target="{target}"/>'
        for identifier, relationship_type, target in items
    )
    return _xml(f'<Relationships xmlns="{PACKAGE_REL_NS}">{children}</Relationships>')


def _content_types() -> bytes:
    overrides = (
        ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
        ("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
        ("/xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"),
        ("/xl/worksheets/sheet1.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
        ("/xl/worksheets/sheet2.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
        ("/xl/worksheets/sheet3.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
        ("/xl/tables/table1.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"),
        ("/xl/tables/table2.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"),
    )
    body = (
        f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(
            f'<Override PartName="{name}" ContentType="{content_type}"/>'
            for name, content_type in overrides
        )
        + "</Types>"
    )
    return _xml(body)


def _core_properties() -> bytes:
    return _xml(
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dcterms:created xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:modified>'
        '<cp:revision>1</cp:revision>'
        "</cp:coreProperties>"
    )


def _workbook() -> bytes:
    return _xml(
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{OFFICE_REL_NS}">'
        '<workbookPr date1904="0"/>'
        '<bookViews><workbookView activeTab="0" firstSheet="0"/></bookViews>'
        "<sheets>"
        '<sheet name="Instructions" sheetId="1" r:id="rId3"/>'
        '<sheet name="Ratings" sheetId="2" r:id="rId4"/>'
        '<sheet name="Decisions" sheetId="3" r:id="rId5"/>'
        "</sheets>"
        '<calcPr calcId="191029" fullCalcOnLoad="1" forceFullCalc="1"/>'
        "</workbook>"
    )


def _styles() -> bytes:
    return _xml(
        f'<styleSheet xmlns="{MAIN_NS}">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="0.00"/></numFmts>'
        '<fonts count="6">'
        '<font><sz val="10"/><color rgb="FF24313A"/><name val="Segoe UI"/><family val="2"/></font>'
        '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Segoe UI"/><family val="2"/></font>'
        '<font><b/><sz val="15"/><color rgb="FF24313A"/><name val="Segoe UI"/><family val="2"/></font>'
        '<font><b/><sz val="10"/><color rgb="FF1F6F78"/><name val="Segoe UI"/><family val="2"/></font>'
        '<font><i/><sz val="9"/><color rgb="FF6E7B83"/><name val="Segoe UI"/><family val="2"/></font>'
        '<font><b/><sz val="10"/><color rgb="FF24313A"/><name val="Segoe UI"/><family val="2"/></font>'
        "</fonts>"
        '<fills count="7">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF4F1EA"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F6F78"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF5E8CF"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFE9EDEE"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF3DFC0"/><bgColor indexed="64"/></patternFill></fill>'
        "</fills>"
        '<borders count="4">'
        '<border><left/><right/><top/><bottom/><diagonal/></border>'
        '<border><left/><right/><top/><bottom style="thin"><color rgb="FF6E7B83"/></bottom><diagonal/></border>'
        '<border><left/><right style="thin"><color rgb="FFFFFFFF"/></right><top/><bottom style="thin"><color rgb="FF1F6F78"/></bottom><diagonal/></border>'
        '<border><left/><right/><top/><bottom style="thin"><color rgb="FFC78C34"/></bottom><diagonal/></border>'
        "</borders>"
        '<cellStyleXfs count="4">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
        '<xf numFmtId="0" fontId="0" fillId="4" borderId="3" applyFill="1" applyBorder="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="5" borderId="0" applyFill="1"/>'
        '<xf numFmtId="0" fontId="5" fillId="6" borderId="0" applyFont="1" applyFill="1"/>'
        "</cellStyleXfs>"
        '<cellXfs count="13">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="3" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="3" borderId="2" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="4" borderId="3" xfId="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="1" fontId="0" fillId="4" borderId="3" xfId="1" applyNumberFormat="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="5" borderId="0" xfId="2" applyFill="1" applyAlignment="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="1" fontId="0" fillId="5" borderId="0" xfId="2" applyNumberFormat="1" applyFill="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="164" fontId="0" fillId="5" borderId="0" xfId="2" applyNumberFormat="1" applyFill="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="4" borderId="3" xfId="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
        '<xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
        "</cellXfs>"
        '<cellStyles count="4">'
        '<cellStyle name="Normal" xfId="0" builtinId="0"/>'
        '<cellStyle name="Input" xfId="1"/>'
        '<cellStyle name="Calculated" xfId="2"/>'
        '<cellStyle name="Warning" xfId="3"/>'
        "</cellStyles>"
        '<dxfs count="3">'
        '<dxf><font><b/><color rgb="FF24313A"/></font><fill><patternFill patternType="solid"><fgColor rgb="FFF3DFC0"/><bgColor indexed="64"/></patternFill></fill></dxf>'
        '<dxf><font><b/><color rgb="FFFFFFFF"/></font><fill><patternFill patternType="solid"><fgColor rgb="FF1F6F78"/><bgColor indexed="64"/></patternFill></fill></dxf>'
        '<dxf><fill><patternFill patternType="solid"><fgColor rgb="FFF4F1EA"/><bgColor indexed="64"/></patternFill></fill></dxf>'
        "</dxfs>"
        '<tableStyles count="1" defaultTableStyle="VoiceScorecard" defaultPivotStyle="PivotStyleLight16">'
        '<tableStyle name="VoiceScorecard" pivot="0" table="1" count="2">'
        '<tableStyleElement type="headerRow" dxfId="1"/>'
        '<tableStyleElement type="firstRowStripe" dxfId="2"/>'
        "</tableStyle>"
        "</tableStyles>"
        "</styleSheet>"
    )


def _sheet_shell(
    *,
    tab_color: str,
    dimension: str,
    columns: str,
    rows: str,
    pane: str = "",
    after_data: str = "",
    table_parts: str = "",
) -> bytes:
    return _xml(
        f'<worksheet xmlns="{MAIN_NS}" xmlns:x="{MAIN_NS}" xmlns:r="{OFFICE_REL_NS}">'
        f'<sheetPr><tabColor rgb="FF{tab_color}"/></sheetPr>'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView showGridLines="0" workbookViewId="0">'
        f"{pane}</sheetView></sheetViews>"
        '<sheetFormatPr defaultRowHeight="18"/>'
        f"<cols>{columns}</cols>"
        f"<x:sheetData>{rows}</x:sheetData>"
        f"{after_data}"
        '<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6" header="0.3" footer="0.3"/>'
        f"{table_parts}"
        "</worksheet>"
    )


def _instructions_sheet() -> bytes:
    row_cells: dict[int, list[str]] = {
        1: [_text_cell("A1", "Voice evaluation scorecard", 1)],
        2: [
            _text_cell(
                "A2",
                "Use this blank workbook for blind listening. Keep completed copies and private mappings outside Git.",
                3,
            )
        ],
        4: [
            _text_cell("A4", "Step", 2),
            _text_cell("B4", "Action", 2),
            _text_cell("C4", "Complete when", 2),
            _text_cell("E4", "No.", 2),
            _text_cell("F4", "Supported style", 2),
        ],
    }
    heights = {1: 28, 2: 22, 4: 24, 13: 24, 21: 24}
    workflow = (
        (1, "Prepare blind labels and the playback order outside this workbook.", "The private label map is stored separately."),
        (2, "Enter one candidate per row on Ratings.", "Blind label, prompt context, style and candidate file are present."),
        (3, "Rate all six measures from 1 to 5.", "Ratings complete shows Complete."),
        (4, "Compare candidates by style on Decisions.", "The Status column shows the next action."),
        (5, "Record the selected blind label and a short decision note.", "One decision is recorded for each evaluated style."),
        (6, "Unblind only after decisions are recorded.", "The private label map remains outside this workbook."),
    )
    for offset, (step, action, complete) in enumerate(workflow, start=5):
        row_cells[offset] = [
            _number_cell(f"A{offset}", step, 11),
            _text_cell(f"B{offset}", action, 12),
            _text_cell(f"C{offset}", complete, 12),
        ]
        heights[offset] = 34
    for style_index, style in enumerate(STYLES, start=1):
        number = style_index + 4
        row_cells.setdefault(number, []).extend(
            [
                _number_cell(f"E{number}", style_index, 11),
                _text_cell(f"F{number}", style, 0),
            ]
        )
        heights.setdefault(number, 22)
    row_cells[13] = [
        _text_cell("A13", "Score", 2),
        _text_cell("B13", "Meaning", 2),
        _text_cell("C13", "Use this score when", 2),
        *row_cells.get(13, []),
    ]
    scale = (
        (1, "Unusable", "The problem is clear enough to reject the candidate."),
        (2, "Weak", "Several problems distract from the intended voice or delivery."),
        (3, "Acceptable", "The candidate is usable with limitations that remain easy to hear."),
        (4, "Strong", "The candidate is convincing with only minor limitations."),
        (5, "Excellent", "No meaningful issue is apparent in this listening pass."),
    )
    for number, (score, meaning, use) in enumerate(scale, start=14):
        row_cells[number] = [
            _number_cell(f"A{number}", score, 11),
            _text_cell(f"B{number}", meaning, 0),
            _text_cell(f"C{number}", use, 12),
            *row_cells.get(number, []),
        ]
        heights[number] = 30
    row_cells[21] = [
        _text_cell("A21", "Measure", 2),
        _text_cell("B21", "Listening question", 2),
        _text_cell("C21", "Direction", 2),
        _text_cell("E21", "Keep private", 2),
        _text_cell("F21", "Public workbook", 2),
    ]
    measures = (
        ("Identity", "Does the candidate resemble the intended speaker?", "Higher is closer."),
        ("Naturalness", "Does the delivery sound like ordinary human speech?", "Higher is more natural."),
        ("Pacing", "Is the speed and pause pattern appropriate for the text?", "Higher is better paced."),
        ("Pronunciation", "Are words and names spoken as intended?", "Higher is more accurate."),
        ("Artifact-free", "Is the audio free of glitches, repetitions and cut words?", "Higher is cleaner."),
        ("Emotion fit", "Does the delivery match the requested style?", "Higher is a better fit."),
    )
    privacy = (
        ("Reference and candidate audio", "No audio files"),
        ("Blind-label and speaker mappings", "Blank table structure"),
        ("Completed ratings and decisions", "Formulas and instructions"),
        ("Listener and speaker identities", "No identity fields"),
    )
    for number, measure in enumerate(measures, start=22):
        row_cells[number] = [
            _text_cell(f"A{number}", measure[0], 0),
            _text_cell(f"B{number}", measure[1], 12),
            _text_cell(f"C{number}", measure[2], 12),
        ]
        privacy_index = number - 22
        if privacy_index < len(privacy):
            row_cells[number].extend(
                [
                    _text_cell(f"E{number}", privacy[privacy_index][0], 12),
                    _text_cell(f"F{number}", privacy[privacy_index][1], 12),
                ]
            )
        heights[number] = 32
    rows = [
        _row(number, row_cells[number], heights.get(number))
        for number in sorted(row_cells)
    ]
    columns = (
        '<col min="1" max="1" width="11" customWidth="1"/>'
        '<col min="2" max="2" width="42" customWidth="1"/>'
        '<col min="3" max="3" width="58" customWidth="1"/>'
        '<col min="4" max="4" width="3" customWidth="1"/>'
        '<col min="5" max="5" width="28" customWidth="1"/>'
        '<col min="6" max="6" width="30" customWidth="1"/>'
    )
    return _sheet_shell(
        tab_color="6E7B83",
        dimension="A1:F27",
        columns=columns,
        rows="".join(rows),
    )


def _ratings_sheet() -> bytes:
    rows = [
        _row(
            1,
            [_text_cell(f"{chr(65 + index)}1", header, 4) for index, header in enumerate(RATING_HEADERS)],
            36,
        )
    ]
    for number in range(2, 102):
        cells = [
            _blank_cell(f"A{number}", 5),
            _blank_cell(f"B{number}", 5),
            _blank_cell(f"C{number}", 10),
            _blank_cell(f"D{number}", 5),
            _blank_cell(f"E{number}", 5),
        ]
        cells.extend(_blank_cell(f"{column}{number}", 6) for column in "FGHIJK")
        cells.extend(
            [
                _formula_cell(
                    f"L{number}",
                    f'IF(COUNTA(A{number}:K{number})=0,"",IF(AND(COUNTA(A{number}:E{number})=5,COUNT(F{number}:K{number})=6),"Complete","Incomplete"))',
                    7,
                ),
                _formula_cell(
                    f"M{number}",
                    f'IF(L{number}="Complete",AVERAGE(F{number}:K{number}),"")',
                    9,
                ),
                _blank_cell(f"N{number}", 10),
            ]
        )
        rows.append(_row(number, cells, 24))
    pane = '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
    columns = (
        '<col min="1" max="1" width="15" customWidth="1"/>'
        '<col min="2" max="2" width="18" customWidth="1"/>'
        '<col min="3" max="3" width="48" customWidth="1"/>'
        '<col min="4" max="4" width="25" customWidth="1"/>'
        '<col min="5" max="5" width="26" customWidth="1"/>'
        '<col min="6" max="11" width="14" customWidth="1"/>'
        '<col min="12" max="12" width="18" customWidth="1"/>'
        '<col min="13" max="13" width="13" customWidth="1"/>'
        '<col min="14" max="14" width="36" customWidth="1"/>'
    )
    style_values = ",".join(STYLES)
    after_data = (
        '<conditionalFormatting sqref="L2:L101">'
        '<cfRule type="containsText" dxfId="0" priority="1" operator="containsText" text="Incomplete">'
        '<formula>NOT(ISERROR(SEARCH("Incomplete",L2)))</formula>'
        "</cfRule></conditionalFormatting>"
        '<dataValidations count="2">'
        '<dataValidation type="list" allowBlank="1" showErrorMessage="1" sqref="D2:D101">'
        f'<formula1>"{style_values}"</formula1></dataValidation>'
        '<dataValidation type="whole" operator="between" allowBlank="1" showErrorMessage="1" '
        'errorStyle="stop" errorTitle="Invalid rating" error="Rating must be a whole number from 1 to 5." '
        'sqref="F2:K101"><formula1>1</formula1><formula2>5</formula2></dataValidation>'
        "</dataValidations>"
    )
    return _sheet_shell(
        tab_color="1F6F78",
        dimension="A1:N101",
        columns=columns,
        rows="".join(rows),
        pane=pane,
        after_data=after_data,
        table_parts='<tableParts count="1"><tablePart r:id="rId1"/></tableParts>',
    )


def _decisions_sheet() -> bytes:
    rows = [
        _row(
            1,
            [_text_cell(f"{chr(65 + index)}1", header, 4) for index, header in enumerate(DECISION_HEADERS)],
            36,
        )
    ]
    for number, style in enumerate(STYLES, start=2):
        rows.append(
            _row(
                number,
                [
                    _text_cell(f"A{number}", style, 7),
                    _formula_cell(
                        f"B{number}",
                        f'COUNTIFS(Ratings!$D$2:$D$101,A{number},Ratings!$A$2:$A$101,"<>")',
                        8,
                    ),
                    _formula_cell(
                        f"C{number}",
                        f'COUNTIFS(Ratings!$D$2:$D$101,A{number},Ratings!$L$2:$L$101,"Complete")',
                        8,
                    ),
                    _formula_cell(
                        f"D{number}",
                        f'IF(OR(B{number}=0,C{number}<B{number}),"",_xlfn.MAXIFS(Ratings!$M$2:$M$101,Ratings!$D$2:$D$101,A{number},Ratings!$L$2:$L$101,"Complete"))',
                        9,
                    ),
                    _formula_cell(
                        f"E{number}",
                        f'IF(D{number}="","",COUNTIFS(Ratings!$D$2:$D$101,A{number},Ratings!$L$2:$L$101,"Complete",Ratings!$M$2:$M$101,D{number}))',
                        8,
                    ),
                    _formula_cell(
                        f"F{number}",
                        f'IF(B{number}=0,"Await candidates",IF(C{number}<B{number},"Finish ratings",IF(G{number}="",IF(E{number}>1,"Review tie","Choose candidate"),IF(COUNTIFS(Ratings!$A$2:$A$101,G{number},Ratings!$D$2:$D$101,A{number},Ratings!$L$2:$L$101,"Complete")=0,"Choose listed candidate",IF(LEN(TRIM(H{number}))=0,"Add decision note","Decision recorded")))))',
                        7,
                    ),
                    _blank_cell(f"G{number}", 5),
                    _blank_cell(f"H{number}", 10),
                ],
                26,
            )
        )
    pane = '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
    columns = (
        '<col min="1" max="1" width="27" customWidth="1"/>'
        '<col min="2" max="3" width="20" customWidth="1"/>'
        '<col min="4" max="5" width="13" customWidth="1"/>'
        '<col min="6" max="6" width="20" customWidth="1"/>'
        '<col min="7" max="7" width="22" customWidth="1"/>'
        '<col min="8" max="8" width="44" customWidth="1"/>'
    )
    return _sheet_shell(
        tab_color="C78C34",
        dimension="A1:H15",
        columns=columns,
        rows="".join(rows),
        pane=pane,
        table_parts='<tableParts count="1"><tablePart r:id="rId1"/></tableParts>',
    )


def _table(table_id: int, name: str, reference: str, headers: tuple[str, ...]) -> bytes:
    columns = "".join(
        f'<tableColumn id="{index}" name="{_attr(header)}"/>'
        for index, header in enumerate(headers, start=1)
    )
    return _xml(
        f'<table xmlns="{MAIN_NS}" id="{table_id}" name="{name}" displayName="{name}" '
        f'ref="{reference}" headerRowCount="1" totalsRowCount="0" totalsRowShown="0">'
        f'<autoFilter ref="{reference}"/>'
        f'<tableColumns count="{len(headers)}">{columns}</tableColumns>'
        '<tableStyleInfo name="VoiceScorecard" showFirstColumn="0" showLastColumn="0" '
        'showRowStripes="1" showColumnStripes="0"/>'
        "</table>"
    )


def _parts() -> tuple[tuple[str, bytes], ...]:
    root_relationships = _relationships(
        (
            ("rId1", f"{OFFICE_REL_NS}/officeDocument", "/xl/workbook.xml"),
            (
                "rId2",
                "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
                "/docProps/core.xml",
            ),
        )
    )
    workbook_relationships = _relationships(
        (
            ("rId1", f"{OFFICE_REL_NS}/styles", "/xl/styles.xml"),
            ("rId3", f"{OFFICE_REL_NS}/worksheet", "/xl/worksheets/sheet1.xml"),
            ("rId4", f"{OFFICE_REL_NS}/worksheet", "/xl/worksheets/sheet2.xml"),
            ("rId5", f"{OFFICE_REL_NS}/worksheet", "/xl/worksheets/sheet3.xml"),
        )
    )
    ratings_relationships = _relationships(
        (("rId1", f"{OFFICE_REL_NS}/table", "/xl/tables/table1.xml"),)
    )
    decisions_relationships = _relationships(
        (("rId1", f"{OFFICE_REL_NS}/table", "/xl/tables/table2.xml"),)
    )
    return (
        ("[Content_Types].xml", _content_types()),
        ("_rels/.rels", root_relationships),
        ("docProps/core.xml", _core_properties()),
        ("xl/workbook.xml", _workbook()),
        ("xl/_rels/workbook.xml.rels", workbook_relationships),
        ("xl/styles.xml", _styles()),
        ("xl/worksheets/sheet1.xml", _instructions_sheet()),
        ("xl/worksheets/sheet2.xml", _ratings_sheet()),
        ("xl/worksheets/_rels/sheet2.xml.rels", ratings_relationships),
        ("xl/tables/table1.xml", _table(1, "RatingsTable", "A1:N101", RATING_HEADERS)),
        ("xl/worksheets/sheet3.xml", _decisions_sheet()),
        ("xl/worksheets/_rels/sheet3.xml.rels", decisions_relationships),
        ("xl/tables/table2.xml", _table(2, "DecisionsTable", "A1:H15", DECISION_HEADERS)),
    )


def write_part(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    """Write one ZIP member with fixed metadata and compression."""
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0
    archive.writestr(info, data, compresslevel=9)


def _zero_external_attributes(data: bytes) -> bytes:
    package = bytearray(data)
    offset = 0
    while True:
        offset = package.find(b"PK\x01\x02", offset)
        if offset < 0:
            return bytes(package)
        struct.pack_into("<I", package, offset + 38, 0)
        name_length, extra_length, comment_length = struct.unpack_from(
            "<HHH", package, offset + 28
        )
        offset += 46 + name_length + extra_length + comment_length


def _build_bytes() -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in _parts():
            write_part(archive, name, data)
    return _zero_external_attributes(stream.getvalue())


def build_scorecard(output: Path) -> None:
    """Write the reproducible public scorecard to ``output``."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_build_bytes())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", type=Path, help="XLSX path to write")
    group.add_argument("--check", type=Path, help="XLSX path to compare byte-for-byte")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.check is not None:
        if not args.check.is_file():
            print(f"missing workbook: {args.check}")
            return 1
        if args.check.read_bytes() != _build_bytes():
            print(f"byte mismatch: {args.check}")
            return 1
        print(f"exact byte match: {args.check}")
        return 0

    output = args.output or DEFAULT_OUTPUT
    build_scorecard(output)
    print(f"wrote deterministic scorecard: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
