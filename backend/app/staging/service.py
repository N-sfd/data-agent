"""Entry point for reading a document's Professional Staging Workbook."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.staging import registry
from app.staging.engine import assemble_workbook, build_dataset
from app.staging.profile import StagingProfile
from app.staging.models import CellValidation, ProcessingMetadata, StagingCell, StagingRecord, StagingWorkbook
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


def pinned_profile(database: Session, document: Document) -> StagingProfile:
    record = _pinned_record(database, document)
    return (
        registry.get_profile(record.profile_id, record.profile_version)
        or registry.get_profile(record.profile_id)
        or registry.generic_profile()
    )


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
    workbook = _with_ai_notice(workbook, ai)
    return _with_ocr_notice(workbook, _ocr_pass_gaps(database, document.id))


def _ocr_pass_gaps(database: Session, document_id: str) -> dict[str, list[int]]:
    """Pages whose optional enhanced OCR pass, or whose word-level OCR
    pass, was unavailable (timed out / failed) — see page_text_extractor."""

    gaps: dict[str, list[int]] = {"enhancement": [], "word_layer": []}
    rows = database.execute(
        select(DocumentPage.page_number, DocumentPage.ocr_layout_json)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    for page_number, layout in rows:
        passes = (layout or {}).get("ocr_passes") or {}
        if passes.get("primary_layout") == "unavailable":
            gaps["word_layer"].append(page_number)
        elif passes.get("enhancement") == "unavailable":
            gaps["enhancement"].append(page_number)
    return gaps


def _with_ocr_notice(workbook: StagingWorkbook, gaps: dict[str, list[int]]) -> StagingWorkbook:
    """A plain-language QA row when an OCR pass was unavailable. The pass-1
    result stands; affected values are already gated by their own OCR
    confidence (unknown or low confidence is Needs Review), so this row
    changes no cell's state."""

    messages = []
    if gaps.get("enhancement"):
        messages.append(
            "Enhanced OCR was unavailable"
            f" (page {', '.join(str(p) for p in gaps['enhancement'])})."
            " Extraction completed using the primary OCR pass; some values may require review."
        )
    if gaps.get("word_layer"):
        messages.append(
            "Word-level OCR was unavailable"
            f" (page {', '.join(str(p) for p in gaps['word_layer'])})."
            " Text positions come from the page OCR without word confidence; values read there require review."
        )
    if not messages:
        return workbook
    return _append_qa_info(
        workbook,
        "qa:ocr_passes",
        {
            "check": "OCR processing",
            "result": "INFO",
            "details": " ".join(messages),
            "action": "Review flagged values against the source image.",
        },
    )


def _append_qa_info(workbook: StagingWorkbook, record_id: str, values: dict) -> StagingWorkbook:
    qa = next((d for d in workbook.datasets if d.role == "qa"), None)
    if qa is None:
        return workbook
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
    qa.records.append(StagingRecord(record_id=record_id, cells=cells))
    return workbook


def compact_for_grid(workbook: StagingWorkbook) -> StagingWorkbook:
    """The workbook as served to the UI: a dataset that declares grid
    fields carries only those cells per record — value and review state,
    computed over every cell first — while provenance, checks and the other
    fields load per record for its detail view (get_staging_record).
    Datasets without grid fields are unchanged."""

    for dataset in workbook.datasets:
        if not dataset.grid_fields:
            continue
        keep = set(dataset.grid_fields) | set(dataset.identity_fields)
        for record in dataset.records:
            record.cells = {
                k: v.model_copy(
                    update={
                        "provenance": None,
                        "raw_value": None,
                        "validation": CellValidation(status=v.validation.status),
                    }
                )
                for k, v in record.cells.items()
                if k in keep
            }
            record.source_columns = []
        dataset.compact = True
    return workbook


def get_staging_record(
    database: Session, document_id: str, dataset_id: str, record_id: str
) -> StagingRecord | None:
    """One fully-validated record of one dataset (every cell, provenance
    and checks) — the detail view of a compact grid row."""

    document = database.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found.")
    profile = pinned_profile(database, document)
    try:
        definition = profile.dataset(dataset_id)
    except KeyError:
        return None
    raws = [
        raw
        for raw in profile.adapter(database, document).records.get(dataset_id, [])
        if raw.record_id == record_id
    ]
    if not raws:
        return None
    return build_dataset(definition, raws).records[0]


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
