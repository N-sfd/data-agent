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
)
from app.services.dashboard_stats import (
    compute_document_confidence,
    compute_document_needs_manual_review,
    compute_document_status,
    compute_review_queue_bucket,
)

router = APIRouter()


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

    return [
        ReviewQueueEntry(
            document_id=document.id,
            original_filename=document.original_filename,
            document_type=document.document_type,
            confidence=compute_document_confidence(
                database, document
            ),
            queue_bucket=compute_review_queue_bucket(
                database, document
            ),
            uploaded_at=document.uploaded_at,
        )
        for document in documents
    ]
