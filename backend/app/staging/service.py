"""Entry point for reading a document's Professional Staging Workbook."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.staging import registry
from app.staging.engine import assemble_workbook
from app.staging.models import ProcessingMetadata, StagingCell, StagingRecord, StagingWorkbook
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
    ai = (document.ingestion_provenance or {}).get("ai_enrichment") or {}
    metadata = ProcessingMetadata(
        document_family=record.document_family,
        document_family_label=record.document_family_label,
        resolution_reasons=reasons,
        resolved_at=record.resolved_at.isoformat() if record.resolved_at else None,
        page_count=document.page_count,
        source_type=source_type_of(document),
        transcription_available=has_text,
        ai_enrichment_status=ai.get("ai_enrichment_status"),
        ai_enrichment_notice=ai.get("notice"),
    )
    workbook = assemble_workbook(
        profile=profile,
        document=document,
        adapter_result=profile.adapter(database, document),
        metadata=metadata,
    )
    return _with_ai_notice(workbook, ai)


def _with_ai_notice(workbook: StagingWorkbook, ai: dict) -> StagingWorkbook:
    """A non-blocking QA row when optional AI enrichment was unavailable.
    Informational: no cell's review state changes because AI didn't run."""

    if ai.get("ai_enrichment_status") not in ("unavailable", "failed"):
        return workbook
    qa = next((d for d in workbook.datasets if d.role == "qa"), None)
    if qa is None:
        return workbook
    notice = ai.get("notice") or {}
    values = {
        "check": "AI enrichment",
        "result": "INFO",
        "details": "AI enrichment unavailable — deterministic results shown."
        + (f" {notice['detail']}" if notice.get("detail") else ""),
        "action": "None required. Technical details are in Processing Details.",
    }
    by_suffix = {column.canonical_field.rsplit(".", 1)[-1]: column for column in qa.columns}
    cells = {
        column.canonical_field: StagingCell(
            canonical_field=column.canonical_field,
            display_label=column.display_label,
            value=values.get(suffix),
            raw_value=values.get(suffix),
        )
        for suffix, column in by_suffix.items()
    }
    qa.records.append(StagingRecord(record_id="qa:ai_enrichment", cells=cells))
    return workbook
