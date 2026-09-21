"""Reviewed-value-aware export and Oracle payload builders.

Distinguishes machine extraction from human-authoritative results:

  extracted_value  → latest / original machine extract
  value            → effective reviewed (or pending machine) value
  review_status    → pending | accepted | edited | rejected | unknown

Business CSV uses ``value``. Rich JSON keeps both. Oracle preview never
treats pending/rejected/unknown as authoritative downstream data.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.services.section_detection import find_nearby_section

AUTHORITATIVE_REVIEW_STATUSES = frozenset({"accepted", "edited"})
NON_AUTHORITATIVE_REVIEW_STATUSES = frozenset(
    {"pending", "rejected", "unknown"}
)

CSV_HEADERS = [
    "field",
    "value",
    "extracted_value",
    "review_status",
    "confidence",
    "validation_status",
    "source_page",
    "section",
    "field_type",
]


def _evidence(field: DocumentMetadataField) -> dict[str, Any]:
    raw = field.evidence_json
    return dict(raw) if isinstance(raw, dict) else {}


def extracted_value_for(field: DocumentMetadataField) -> str:
    evidence = _evidence(field)
    machine = evidence.get("machine_value")
    if machine is not None and str(machine) != "":
        return str(machine)
    if field.original_value:
        return str(field.original_value)
    return str(field.value or "")


def validation_status_for(field: DocumentMetadataField) -> str:
    evidence = _evidence(field)
    validation = evidence.get("validation")
    if isinstance(validation, dict) and validation.get("status"):
        return str(validation["status"])
    status = evidence.get("validation_status")
    if status:
        return str(status)
    return "passed"


def source_page_for(field: DocumentMetadataField) -> int:
    evidence = _evidence(field)
    page = evidence.get("page_number")
    if isinstance(page, int) and page > 0:
        return page
    try:
        return int(page)
    except (TypeError, ValueError):
        return 1


def is_authoritative(field: DocumentMetadataField) -> bool:
    return (field.review_status or "pending") in AUTHORITATIVE_REVIEW_STATUSES


def section_for(
    field: DocumentMetadataField,
    *,
    page_text_by_number: dict[int, str] | None = None,
) -> str:
    """Nearby heading for this field — from evidence if already computed
    at extraction time, otherwise best-effort from the page text."""

    evidence = _evidence(field)
    section = evidence.get("section")
    if section:
        return str(section)

    if not page_text_by_number:
        return ""

    page_text = page_text_by_number.get(source_page_for(field), "")
    if not page_text:
        return ""

    found = find_nearby_section(
        page_text,
        extracted_value_for(field) or str(field.value or ""),
    )
    return found or ""


def field_to_export_record(
    field: DocumentMetadataField,
    *,
    page_text_by_number: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Rich export row matching the reviewed-value contract."""

    status = field.review_status or "pending"
    return {
        "field": field.label,
        "field_key": field.field_key,
        "field_group": field.field_group,
        "section": section_for(field, page_text_by_number=page_text_by_number),
        "extracted_value": extracted_value_for(field),
        "value": field.value,
        "review_status": status,
        "confidence": field.confidence,
        "validation": {"status": validation_status_for(field)},
        "source": {"page": source_page_for(field)},
        "authoritative": status in AUTHORITATIVE_REVIEW_STATUSES,
    }


def build_document_export(
    *,
    document: Document,
    fields: list[DocumentMetadataField],
    authoritative_only: bool = False,
) -> dict[str, Any]:
    selected = (
        [field for field in fields if is_authoritative(field)]
        if authoritative_only
        else list(fields)
    )
    records = [field_to_export_record(field) for field in selected]
    skipped = [
        {
            "field": field.label,
            "field_key": field.field_key,
            "review_status": field.review_status or "pending",
            "reason": "not_authoritative",
        }
        for field in fields
        if authoritative_only and not is_authoritative(field)
    ]
    return {
        "document_id": document.id,
        "document_filename": document.original_filename,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authoritative_only": authoritative_only,
        "field_count": len(records),
        "fields": records,
        "skipped": skipped,
    }


def build_export_csv(
    fields: list[DocumentMetadataField],
    *,
    authoritative_only: bool = False,
    page_text_by_number: dict[int, str] | None = None,
) -> str:
    """Business CSV: effective reviewed ``value`` is the primary column."""

    selected = (
        [field for field in fields if is_authoritative(field)]
        if authoritative_only
        else list(fields)
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()
    for field in selected:
        record = field_to_export_record(
            field, page_text_by_number=page_text_by_number
        )
        writer.writerow(
            {
                "field": record["field"],
                "section": record["section"],
                "field_type": record["field_group"],
                "value": record["value"],
                "extracted_value": record["extracted_value"],
                "review_status": record["review_status"],
                "confidence": record["confidence"],
                "validation_status": record["validation"]["status"],
                "source_page": record["source"]["page"],
            }
        )
    return buffer.getvalue()


def build_fields_wide_csv(
    fields: list[DocumentMetadataField],
    *,
    authoritative_only: bool = False,
) -> str:
    """Business-data CSV: one header row of field keys, one data row."""

    selected = (
        [field for field in fields if is_authoritative(field)]
        if authoritative_only
        else list(fields)
    )
    # Prefer stable keys; fall back to labels when key missing.
    headers: list[str] = []
    values: list[str] = []
    for field in selected:
        headers.append(field.field_key or field.label)
        value = field.value
        values.append("" if value is None else str(value))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerow(values)
    return buffer.getvalue()


def _safe_sheet_title(name: str, used: set[str]) -> str:
    cleaned = "".join(
        ch if ch.isalnum() or ch in " -_" else "_" for ch in (name or "Sheet")
    ).strip() or "Sheet"
    cleaned = cleaned[:28]
    candidate = cleaned
    index = 2
    while candidate.lower() in used:
        candidate = f"{cleaned[:24]}_{index}"
        index += 1
    used.add(candidate.lower())
    return candidate


def build_export_xlsx(
    *,
    document: Document,
    fields: list[DocumentMetadataField],
    tables: list[Any] | None = None,
    authoritative_only: bool = False,
    page_text_by_number: dict[int, str] | None = None,
) -> bytes:
    """Complete workbook: Document, Fields (wide), table sheets, Source Evidence."""

    from openpyxl import Workbook

    selected = (
        [field for field in fields if is_authoritative(field)]
        if authoritative_only
        else list(fields)
    )
    workbook = Workbook()
    used_titles: set[str] = set()

    document_sheet = workbook.active
    document_sheet.title = _safe_sheet_title("Document", used_titles)
    document_sheet.append(["property", "value"])
    document_sheet.append(["document_id", document.id])
    document_sheet.append(["filename", document.original_filename])
    document_sheet.append(["page_count", document.page_count])
    document_sheet.append(
        ["generated_at", datetime.now(timezone.utc).isoformat()]
    )

    fields_sheet = workbook.create_sheet(_safe_sheet_title("Fields", used_titles))
    headers = [field.field_key or field.label for field in selected]
    values = [
        "" if field.value is None else str(field.value) for field in selected
    ]
    fields_sheet.append(headers)
    fields_sheet.append(values)

    for table in tables or []:
        title = getattr(table, "display_name", None) or getattr(
            table, "target_key", None
        ) or "Table"
        sheet = workbook.create_sheet(_safe_sheet_title(str(title), used_titles))
        columns = list(getattr(table, "columns_json", None) or [])
        rows = list(getattr(table, "rows_json", None) or [])
        if not columns and rows and isinstance(rows[0], dict):
            columns = list(rows[0].keys())
        sheet.append([str(col) for col in columns])
        for row in rows:
            if isinstance(row, dict):
                sheet.append([row.get(col, "") for col in columns])
            elif isinstance(row, (list, tuple)):
                sheet.append(list(row))
            else:
                sheet.append([str(row)])

    evidence_sheet = workbook.create_sheet(
        _safe_sheet_title("Source Evidence", used_titles)
    )
    evidence_sheet.append(
        [
            "document",
            "field",
            "field_key",
            "section",
            "field_type",
            "source_page",
            "raw_ocr",
            "normalized_value",
            "extracted_value",
            "value",
            "confidence",
            "validation_status",
            "review_status",
            "extraction_method",
        ]
    )
    for field in selected:
        evidence = _evidence(field)
        evidence_sheet.append(
            [
                document.original_filename,
                field.label,
                field.field_key,
                section_for(field, page_text_by_number=page_text_by_number),
                field.field_group,
                source_page_for(field),
                evidence.get("raw_ocr") or evidence.get("source_text") or "",
                evidence.get("normalized_value") or field.value or "",
                extracted_value_for(field),
                field.value,
                field.confidence,
                validation_status_for(field),
                field.review_status or "pending",
                field.extraction_method
                or evidence.get("extraction_method")
                or "",
            ]
        )

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_oracle_payload_preview(
    *,
    document: Document,
    fields: list[DocumentMetadataField],
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview Oracle-bound payload — never includes pending/rejected.

    Explicit Send to Oracle remains a separate future step; this endpoint
    only builds and validates the preview.
    """

    authoritative = [field for field in fields if is_authoritative(field)]
    skipped = [
        {
            "field": field.label,
            "field_key": field.field_key,
            "review_status": field.review_status or "pending",
            "reason": "pending_or_rejected_not_sent_downstream",
        }
        for field in fields
        if not is_authoritative(field)
    ]

    header: dict[str, Any] = {}
    for field in authoritative:
        header[field.field_key] = field.value

    return {
        "document_id": document.id,
        "source_document": document.original_filename,
        "erp_target": "Oracle Fusion Cloud Procurement",
        "mode": "preview",
        "dry_run": dry_run,
        "send_allowed": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "excluded_statuses": sorted(NON_AUTHORITATIVE_REVIEW_STATUSES),
        "contract_header": header,
        "fields": [field_to_export_record(field) for field in authoritative],
        "skipped": skipped,
        "authoritative_count": len(authoritative),
        "skipped_count": len(skipped),
        "ready_to_send": len(authoritative) > 0 and len(skipped) == 0,
    }
