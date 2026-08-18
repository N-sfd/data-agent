from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    total_documents: int
    completed: int
    review_required: int
    processing: int

    extraction_accuracy: float | None
    average_processing_seconds: float | None
    human_review_rate: float | None
    fields_extracted: int

    review_completion_rate: float | None
    ocr_accuracy: float | None
    clause_extraction_accuracy: float | None
    fields_extracted_today: int
    documents_requiring_manual_review: int


ReviewQueueBucket = Literal[
    "high", "medium", "low", "rejected", "unknown"
]


class ReviewQueueEntry(BaseModel):
    document_id: str
    original_filename: str
    document_type: str | None
    confidence: float | None
    queue_bucket: ReviewQueueBucket
    uploaded_at: datetime
