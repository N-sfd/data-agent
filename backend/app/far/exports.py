"""FAR Part 52 exports: the transformation workbook (01–07 + 99), one CSV
per sheet, and the canonical model as JSON. Built from the persisted
canonical records — never from a reference workbook."""

from __future__ import annotations

import csv
import io
import json

from app.far import views
from app.far.oracle_map import NOTICE, TITLE
from app.models.document_far_record import DocumentFarRecord

SHEETS = {
    "01_FAR_STAGING": "FAR Part 52 — Grouped Professional Staging",
    "02_ORACLE_MAPPING": None,
    "03_VALIDATION": None,
    "99_LONG_TEXT": None,
    "04_STRUCTURED_FAR": "FAR Part 52 — Structured Clause / Provision Extraction",
    "05_EXTRACTION_GUIDE": None,
    "06_CANONICAL_MODEL": "Canonical FAR Transformation Model",
    "07_ORACLE_OUTPUT_MAP": TITLE,
    "08_BUSINESS_EXPORT": "FAR Part 52 — Business Export",
}
SUBTITLES = {
    "01_FAR_STAGING": "One FAR record per row, structural alternates on their own rows after their basic clause. "
    "Text is kept verbatim (never rewritten). Paragraph/Subparagraph remain the last fields.",
    "04_STRUCTURED_FAR": "One FAR record per row. Dates, prescriptions, structural alternates and embedded FAR "
    "references are separated; headings and text are kept intact.",
    "06_CANONICAL_MODEL": "System-neutral canonical layer between FAR extraction and downstream Oracle output. "
    "Alternates are separate records linked by Basic Clause Key; structural and reserved records are kept with "
    "Load Eligible = NO.",
    "07_ORACLE_OUTPUT_MAP": NOTICE,
    "08_BUSINESS_EXPORT": (
        "Final business columns only. Intent, Start Date, Attribute Category and Attribute 1 "
        "stay blank until an approved rule or Oracle target template supports them. "
        "Text is complete in CSV and JSON; Excel cells follow the existing long-text limit and 99_LONG_TEXT."
    ),
}


def sheet_rows(sheet: str, rows: list[DocumentFarRecord], summary: dict | None) -> tuple[tuple[str, ...], list[dict]]:
    if sheet == "01_FAR_STAGING":
        return views.STAGING_COLUMNS, [views.staging_row(r) for r in rows]
    if sheet == "02_ORACLE_MAPPING":
        return views.ORACLE_MAPPING_COLUMNS, [views.oracle_mapping_row(r) for r in rows]
    if sheet == "03_VALIDATION":
        return views.VALIDATION_COLUMNS, views.validation_rows(rows, summary)
    if sheet == "99_LONG_TEXT":
        return views.LONG_TEXT_COLUMNS, views.long_text_rows(rows)
    if sheet == "04_STRUCTURED_FAR":
        return views.STRUCTURED_COLUMNS, [views.structured_row(r) for r in rows]
    if sheet == "05_EXTRACTION_GUIDE":
        columns = ("Field", "Extraction / Formatting Rule", "Data Agent Use")
        return columns, [dict(zip(columns, row)) for row in views.EXTRACTION_GUIDE]
    if sheet == "06_CANONICAL_MODEL":
        return views.CANONICAL_COLUMNS, [views.canonical_row(r) for r in rows]
    if sheet == "07_ORACLE_OUTPUT_MAP":
        return views.OUTPUT_MAP_COLUMNS, views.output_map_rows()
    if sheet == "08_BUSINESS_EXPORT":
        return views.BUSINESS_COLUMNS, [views.business_row(r) for r in rows]
    raise KeyError(sheet)


def build_far_workbook(rows: list[DocumentFarRecord], summary: dict | None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    wb.remove(wb.active)
    for sheet, title in SHEETS.items():
        ws = wb.create_sheet(sheet)
        columns, records = sheet_rows(sheet, rows, summary)
        if title:
            ws.append([title])
            ws.append([SUBTITLES.get(sheet)])
            ws.append([])
            ws["A1"].font = Font(bold=True, size=13)
        ws.append(list(columns))
        header_row = ws.max_row
        for cell in ws[header_row]:
            cell.font = Font(bold=True)
        for record in records:
            values = []
            for column in columns:
                value = record.get(column)
                if isinstance(value, str):
                    # A whole long text lives in 99_LONG_TEXT; the cell
                    # carries its first chunk (Excel's cell limit).
                    if len(value) > views.LONG_TEXT_CHUNK and sheet != "99_LONG_TEXT":
                        value = value[: views.LONG_TEXT_CHUNK]
                    value = ILLEGAL_CHARACTERS_RE.sub("", value)
                values.append(value)
            ws.append(values)
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
        for index, column in enumerate(columns, start=1):
            letter = ws.cell(row=header_row, column=index).column_letter
            wide = column in (
                "Actual Section Text",
                "Source Text",
                "Text",
                "Description",
                "Transformation Rule",
                "Notes",
                "Extraction / Formatting Rule",
            )
            ws.column_dimensions[letter].width = 70 if wide else 22
        for row in ws.iter_rows(min_row=header_row + 1):
            for cell in row:
                cell.alignment = Alignment(wrap_text=False, vertical="top")
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_far_csv(sheet: str, rows: list[DocumentFarRecord], summary: dict | None) -> str:
    columns, records = sheet_rows(sheet, rows, summary)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue()


def build_far_json(rows: list[DocumentFarRecord], summary: dict | None, document: dict) -> str:
    payload = {
        "document": document,
        "profile": "far_part_52@1",
        "summary": views.overview(rows, summary),
        "canonical_model": [
            {
                **views.canonical_row(r),
                "Official Heading": r.official_heading,
                "Clause / Provision": r.clause_type,
                "Prescription": r.prescription,
                "Alternate Heading": r.alternate_heading,
                "Alternate Instruction": r.alternate_instruction,
                "Section": r.subpart,
                "Subsection": r.subsection,
                "Embedded FAR References": list(r.embedded_references or []),
                "Source Locator": r.provenance_json,
            }
            for r in rows
        ],
        "validation": views.validation_rows(rows, summary),
        "oracle_output_mapping": {"title": TITLE, "notice": NOTICE, "rows": views.output_map_rows()},
        "business_export": [views.business_row(r) for r in rows],
    }
    return json.dumps(payload, ensure_ascii=False, indent=1)


CSV_SHEETS = (
    "01_FAR_STAGING",
    "02_ORACLE_MAPPING",
    "03_VALIDATION",
    "04_STRUCTURED_FAR",
    "06_CANONICAL_MODEL",
    "07_ORACLE_OUTPUT_MAP",
    "08_BUSINESS_EXPORT",
)
