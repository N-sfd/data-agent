from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField

COMPLETED_PROCESSING_STATUSES = frozenset(
    {"completed", "completed_with_warnings"}
)


def compute_document_status(
    database: Session, document: Document
) -> str:
    """One of "processing" | "review_required" | "completed"."""

    if document.processing_status not in (
        COMPLETED_PROCESSING_STATUSES
    ):
        return "processing"

    if document.document_type is None:
        return "review_required"

    has_pending = database.scalar(
        select(DocumentMetadataField.id)
        .where(
            DocumentMetadataField.document_id == document.id,
            DocumentMetadataField.review_status == "pending",
        )
        .limit(1)
    )

    if has_pending is not None:
        return "review_required"

    return "completed"


def compute_document_confidence(
    database: Session, document: Document
) -> float | None:
    fields = list(
        database.scalars(
            select(DocumentMetadataField.confidence).where(
                DocumentMetadataField.document_id == document.id
            )
        )
    )

    if fields:
        return sum(fields) / len(fields)

    return document.classification_confidence
