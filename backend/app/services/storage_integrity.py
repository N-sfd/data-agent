"""DB ↔ storage integrity reporting for ops / production hardening."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.document import Document
from app.services.document_storage import (
    classify_source_location,
    is_remote_storage_configured,
)


@dataclass(frozen=True)
class DocumentSourceReport:
    document_id: str
    original_filename: str
    stored_filename: str
    location: str  # local | remote_only | missing
    source_status: str  # available | missing


def audit_document_sources(
    database: Session, settings: Settings, *, limit: int | None = None
) -> list[DocumentSourceReport]:
    query = select(Document).order_by(Document.uploaded_at.desc())
    if limit is not None:
        query = query.limit(limit)

    reports: list[DocumentSourceReport] = []
    for document in database.scalars(query):
        location = classify_source_location(
            settings, stored_filename=document.stored_filename
        )
        reports.append(
            DocumentSourceReport(
                document_id=document.id,
                original_filename=document.original_filename,
                stored_filename=document.stored_filename,
                location=location,
                source_status=(
                    "available" if location != "missing" else "missing"
                ),
            )
        )
    return reports


def storage_integrity_summary(
    database: Session, settings: Settings, *, sample_limit: int = 25
) -> dict:
    reports = audit_document_sources(database, settings)
    by_location = {"local": 0, "remote_only": 0, "missing": 0}
    missing: list[dict] = []

    for report in reports:
        by_location[report.location] = by_location.get(report.location, 0) + 1
        if report.location == "missing" and len(missing) < sample_limit:
            missing.append(
                {
                    "document_id": report.document_id,
                    "original_filename": report.original_filename,
                    "stored_filename": report.stored_filename,
                }
            )

    return {
        "remote_storage_configured": is_remote_storage_configured(settings),
        "total_documents": len(reports),
        "available": by_location["local"] + by_location["remote_only"],
        "missing": by_location["missing"],
        "by_location": by_location,
        "missing_sample": missing,
    }
