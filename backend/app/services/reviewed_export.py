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


def field_to_export_record(field: DocumentMetadataField) -> dict[str, Any]:
    """Rich export row matching the reviewed-value contract."""

    status = field.review_status or "pending"
    return {
        "field": field.label,
        "field_key": field.field_key,
        "field_group": field.field_group,
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
        record = field_to_export_record(field)
        writer.writerow(
            {
                "field": record["field"],
                "value": record["value"],
                "extracted_value": record["extracted_value"],
                "review_status": record["review_status"],
                "confidence": record["confidence"],
                "validation_status": record["validation"]["status"],
                "source_page": record["source"]["page"],
            }
        )
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
