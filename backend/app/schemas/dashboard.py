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
