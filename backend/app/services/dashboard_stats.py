from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField

COMPLETED_PROCESSING_STATUSES = frozenset(
    {"completed", "completed_with_warnings"}
)

LOW_CONFIDENCE_THRESHOLD = 0.8
NEEDS_ATTENTION_STATUSES = frozenset({"rejected", "unknown"})


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


def compute_document_needs_manual_review(
    database: Session, document: Document
) -> bool:
    """True if any field is low-confidence, rejected, or unknown."""

    low_confidence = database.scalar(
        select(DocumentMetadataField.id)
        .where(
            DocumentMetadataField.document_id == document.id,
            DocumentMetadataField.confidence
            < LOW_CONFIDENCE_THRESHOLD,
        )
        .limit(1)
    )

    if low_confidence is not None:
        return True

    needs_attention = database.scalar(
        select(DocumentMetadataField.id)
        .where(
            DocumentMetadataField.document_id == document.id,
            DocumentMetadataField.review_status.in_(
                NEEDS_ATTENTION_STATUSES
            ),
        )
        .limit(1)
    )

    return needs_attention is not None


def compute_review_queue_bucket(
    database: Session, document: Document
) -> str:
    """One of "rejected" | "unknown" | "high" | "medium" | "low"."""

    has_rejected = database.scalar(
        select(DocumentMetadataField.id)
        .where(
            DocumentMetadataField.document_id == document.id,
            DocumentMetadataField.review_status == "rejected",
        )
        .limit(1)
    )

    if has_rejected is not None:
        return "rejected"

    has_unknown = database.scalar(
        select(DocumentMetadataField.id)
        .where(
            DocumentMetadataField.document_id == document.id,
            DocumentMetadataField.review_status == "unknown",
        )
        .limit(1)
    )

    if has_unknown is not None:
        return "unknown"

    confidence = compute_document_confidence(database, document)

    if confidence is None:
        return "low"

    if confidence >= 0.95:
        return "high"

    if confidence >= LOW_CONFIDENCE_THRESHOLD:
        return "medium"

    return "low"
