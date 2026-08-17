from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database
from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.schemas.dashboard import DashboardStatsResponse
from app.services.dashboard_stats import compute_document_status

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

    for document in documents:
        status = compute_document_status(database, document)

        if status == "completed":
            completed += 1
        elif status == "review_required":
            review_required += 1
        else:
            processing += 1

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

    durations = [
        document.processing_duration_seconds
        for document in documents
        if document.processing_duration_seconds is not None
    ]

    average_processing_seconds = (
        sum(durations) / len(durations) if durations else None
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
    )
