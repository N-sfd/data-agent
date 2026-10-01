"""Generic Professional Excel / dataset CSV built from any StagingWorkbook —
used by profiles without a bespoke export (contract_v3 keeps its unchanged
V3 workbook). Every business sheet carries the value plus its page,
evidence and review status, so the export stays source-grounded."""

from __future__ import annotations

import csv
import io
import re

from app.staging.models import StagingDataset, StagingWorkbook

# Excel limits: control characters cannot be stored, and a cell holds at
# most 32,767 characters. CSV/JSON keep the text unchanged.
_XLSX_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_XLSX_CELL_LIMIT = 32_767


def _xlsx_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = _XLSX_ILLEGAL.sub(" ", value)
    if len(text) > _XLSX_CELL_LIMIT:
        note = f" … [truncated for Excel: {len(text):,} characters in full — see the CSV or JSON export]"
        text = text[: _XLSX_CELL_LIMIT - len(note)] + note
    return text

# Excel forbids these in sheet names ("Customer / Bill-To") and caps them at 31.
_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def _sheet_title(name: str, taken: list[str]) -> str:
    base = re.sub(r"\s+", " ", _INVALID_SHEET_CHARS.sub("-", name)).strip(" '")[:31] or "Sheet"
    title, n = base, 2
    while title.lower() in (t.lower() for t in taken):
        suffix = f" ({n})"
        title, n = base[: 31 - len(suffix)] + suffix, n + 1
    return title


def _headers(dataset: StagingDataset) -> list[str]:
    headers = [column.display_label for column in dataset.columns]
    if dataset.role == "business":
        headers += ["Source Page", "Evidence", "Review Status"]
    return headers


def _rows(dataset: StagingDataset) -> list[list[object]]:
    rows: list[list[object]] = []
    for record in dataset.records:
        cells = [record.cells[c.canonical_field] for c in dataset.columns]
        row: list[object] = [cell.value for cell in cells]
        if dataset.role == "business":
            provenance = next((cell.provenance for cell in cells if cell.provenance), None)
            row += [
                provenance.source_page if provenance else None,
                provenance.evidence_text if provenance else None,
                record.record_status,
            ]
        rows.append(row)
    return rows


def find_dataset(workbook: StagingWorkbook, dataset_id: str) -> StagingDataset | None:
    return next((d for d in workbook.datasets if d.dataset_id == dataset_id), None)


def build_dataset_csv(dataset: StagingDataset) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_headers(dataset))
    writer.writerows(_rows(dataset))
    return buffer.getvalue()


def build_workbook_xlsx(workbook: StagingWorkbook) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    readme = wb.active
    readme.title = "README"
    readme.append(["Document", workbook.document_filename])
    readme.append(["Profile", f"{workbook.profile.display_name} ({workbook.profile.profile_id}@{workbook.profile.profile_version})"])
    readme.append(["Outcome", workbook.outcome.title])
    readme.append(["", workbook.outcome.message])
    readme.append([])
    readme.append(["PROVENANCE", "Every business value carries its source page and evidence."])
    readme.append(["REVIEW STATUS", "Verified / Needs Review / Missing — never inferred from OCR confidence."])

    for dataset in workbook.datasets:
        sheet = wb.create_sheet(title=_sheet_title(dataset.display_name, wb.sheetnames))
        sheet.append(_headers(dataset))
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in _rows(dataset):
            sheet.append([_xlsx_value(value) for value in row])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
