"""Entry point for reading a document's Professional Staging Workbook."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.staging import registry
from app.staging.engine import assemble_workbook
from app.staging.models import ProcessingMetadata, StagingWorkbook
from app.staging.provenance import source_type_of
from app.staging.preparation import prepare_staging


def _pinned_record(database: Session, document: Document) -> DocumentStagingWorkbook:
    record = database.scalars(
        select(DocumentStagingWorkbook).where(DocumentStagingWorkbook.document_id == document.id)
    ).first()
    if record is None:
        # Documents extracted before profiles existed: pin on first read so
        # every later read (and later profile versions) stays consistent.
        record = prepare_staging(database, document).record
    return record


def get_staging_workbook(database: Session, document_id: str) -> StagingWorkbook:
    document = database.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found.")

    record = _pinned_record(database, document)
    reasons = list(record.resolution_reasons or [])
    profile = registry.get_profile(record.profile_id, record.profile_version)
    if profile is None:
        profile = registry.get_profile(record.profile_id) or registry.generic_profile()
        reasons.append(
            f"Pinned profile {record.profile_id}@{record.profile_version} is no longer "
            f"registered; rendered with {profile.key}."
        )

    has_text = (
        database.scalar(
            select(DocumentPage.id)
            .where(DocumentPage.document_id == document.id, DocumentPage.final_text != "")
            .limit(1)
        )
        is not None
    )
    metadata = ProcessingMetadata(
        document_family=record.document_family,
        document_family_label=record.document_family_label,
        resolution_reasons=reasons,
        resolved_at=record.resolved_at.isoformat() if record.resolved_at else None,
        page_count=document.page_count,
        source_type=source_type_of(document),
        transcription_available=has_text,
    )
    return assemble_workbook(
        profile=profile,
        document=document,
        adapter_result=profile.adapter(database, document),
        metadata=metadata,
    )
