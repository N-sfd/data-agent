"""Generic Professional Excel / dataset CSV built from any StagingWorkbook —
used by profiles without a bespoke export (contract_v3 keeps its unchanged
V3 workbook). Every business sheet carries the value plus its page,
evidence and review status, so the export stays source-grounded."""

from __future__ import annotations

import csv
import io

from app.staging.models import StagingDataset, StagingWorkbook


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
        sheet = wb.create_sheet(title=dataset.display_name[:31])
        sheet.append(_headers(dataset))
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in _rows(dataset):
            sheet.append(row)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
