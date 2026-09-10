from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database
from app.models.document import Document
from app.models.document_clause import DocumentClause
from app.models.document_metadata_field import DocumentMetadataField
from app.models.document_page import DocumentPage
from app.schemas.dashboard import (
    DashboardStatsResponse,
    ReviewQueueEntry,
    ReviewQueueFieldItem,
)
from app.services.dashboard_stats import (
    compute_document_confidence,
    compute_document_needs_manual_review,
    compute_document_status,
    compute_review_queue_bucket,
)
from app.services.review_routing import human_reason_labels

router = APIRouter()


def _field_review_meta(field: DocumentMetadataField) -> dict:
    evidence = field.evidence_json or {}
    decision = evidence.get("review_decision") or {}
    reasons = list(decision.get("reasons") or [])
    page_number = None
    if isinstance(evidence.get("page_number"), int):
        page_number = evidence["page_number"]
    return {
        "reasons": reasons,
        "priority": decision.get("priority") or "medium",
        "decision_status": decision.get("status") or "needs_review",
        "page_number": page_number,
    }


def _review_href(document_id: str, *, field_key: str | None = None) -> str:
    base = f"/extraction/new?documentId={document_id}"
    if field_key:
        return f"{base}&focus={field_key}"
    return base


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    database: Session = Depends(get_database),
) -> DashboardStatsResponse:
    documents = list(database.scalars(select(Document)))

    total_documents = len(documents)
    completed = 0
    review_required = 0
    processing = 0
    documents_requiring_manual_review = 0

    for document in documents:
        status = compute_document_status(database, document)

        if status == "completed":
            completed += 1
        elif status == "review_required":
            review_required += 1
        else:
            processing += 1

        if compute_document_needs_manual_review(database, document):
            documents_requiring_manual_review += 1

    fields = list(database.scalars(select(DocumentMetadataField)))
    fields_extracted = len(fields)

    extraction_accuracy = (
        sum(field.confidence for field in fields) / len(fields)
        if fields
        else None
    )

    corrected_fields = sum(
        1
        for field in fields
        if field.review_status in {"edited", "rejected"}
    )

    human_review_rate = (
        (corrected_fields / len(fields)) * 100 if fields else None
    )

    reviewed_fields = sum(
        1 for field in fields if field.review_status != "pending"
    )

    review_completion_rate = (
        (reviewed_fields / len(fields)) * 100 if fields else None
    )

    today = datetime.now(timezone.utc).date()
    fields_extracted_today = sum(
        1
        for field in fields
        if field.extracted_at.date() == today
    )

    durations = [
        document.processing_duration_seconds
        for document in documents
        if document.processing_duration_seconds is not None
    ]

    average_processing_seconds = (
        sum(durations) / len(durations) if durations else None
    )

    pages = list(
        database.scalars(
            select(DocumentPage).where(
                DocumentPage.ocr_attempted.is_(True)
            )
        )
    )

    ocr_accuracy = (
        sum(1 for page in pages if page.ocr_succeeded)
        / len(pages)
        * 100
        if pages
        else None
    )

    clause_confidences = list(
        database.scalars(select(DocumentClause.confidence))
    )

    clause_extraction_accuracy = (
        sum(clause_confidences) / len(clause_confidences)
        if clause_confidences
        else None
    )

    return DashboardStatsResponse(
        total_documents=total_documents,
        completed=completed,
        review_required=review_required,
        processing=processing,
        extraction_accuracy=extraction_accuracy,
        average_processing_seconds=average_processing_seconds,
        human_review_rate=human_review_rate,
        fields_extracted=fields_extracted,
        review_completion_rate=review_completion_rate,
        ocr_accuracy=ocr_accuracy,
        clause_extraction_accuracy=clause_extraction_accuracy,
        fields_extracted_today=fields_extracted_today,
        documents_requiring_manual_review=documents_requiring_manual_review,
    )


@router.get(
    "/review-queue", response_model=list[ReviewQueueEntry]
)
async def get_review_queue(
    database: Session = Depends(get_database),
) -> list[ReviewQueueEntry]:
    documents = list(
        database.scalars(
            select(Document).order_by(Document.uploaded_at.desc())
        )
    )

    entries: list[ReviewQueueEntry] = []
    for document in documents:
        if compute_document_status(database, document) != "review_required":
            continue

        fields = list(
            database.scalars(
                select(DocumentMetadataField).where(
                    DocumentMetadataField.document_id == document.id
                )
            )
        )
        pending = [field for field in fields if field.review_status == "pending"]
        attention = 0
        reason_counts: dict[str, int] = {}
        for field in pending:
            meta = _field_review_meta(field)
            if meta["decision_status"] == "needs_review" or meta["reasons"]:
                attention += 1
            for reason in meta["reasons"]:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        top_reasons = [
            reason
            for reason, _ in sorted(
                reason_counts.items(), key=lambda item: (-item[1], item[0])
            )[:3]
        ]

        entries.append(
            ReviewQueueEntry(
                document_id=document.id,
                original_filename=document.original_filename,
                document_type=document.document_type,
                confidence=compute_document_confidence(database, document),
                queue_bucket=compute_review_queue_bucket(database, document),
                uploaded_at=document.uploaded_at,
                pending_field_count=len(pending),
                attention_field_count=attention,
                top_reasons=human_reason_labels(top_reasons),
                review_href=_review_href(document.id),
            )
        )
    return entries


@router.get(
    "/review-queue/fields",
    response_model=list[ReviewQueueFieldItem],
)
async def get_review_queue_fields(
    database: Session = Depends(get_database),
) -> list[ReviewQueueFieldItem]:
    """Field-level Review Queue for target + contract pending items."""

    documents = {
        document.id: document
        for document in database.scalars(select(Document)).all()
    }
    fields = list(
        database.scalars(
            select(DocumentMetadataField)
            .where(DocumentMetadataField.review_status == "pending")
            .order_by(DocumentMetadataField.extracted_at.desc())
        )
    )

    items: list[ReviewQueueFieldItem] = []
    for field in fields:
        document = documents.get(field.document_id)
        if document is None:
            continue
        meta = _field_review_meta(field)
        items.append(
            ReviewQueueFieldItem(
                document_id=field.document_id,
                original_filename=document.original_filename,
                field_key=field.field_key,
                label=field.label,
                value=field.value,
                confidence=field.confidence,
                confidence_band=field.confidence_band,
                review_status=field.review_status,
                extraction_source=field.extraction_source,
                extraction_method=field.extraction_method,
                reasons=meta["reasons"],
                reason_labels=human_reason_labels(meta["reasons"]),
                priority=meta["priority"],
                decision_status=meta["decision_status"],
                page_number=meta["page_number"],
                review_href=_review_href(
                    field.document_id, field_key=field.field_key
                ),
            )
        )

    priority_rank = {"low": 0, "medium": 1, "high": 2}
    items.sort(
        key=lambda item: (
            priority_rank.get(item.priority, 1),
            -item.confidence,
            item.original_filename,
        )
    )
    return items
