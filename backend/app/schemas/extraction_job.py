from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StartExtractionJobRequest(BaseModel):
    target_ids: list[str] = Field(min_length=1)
    use_ai_fallback: bool = True


class ExtractionJobResponse(BaseModel):
    id: int
    document_id: str
    job_type: str
    status: str
    stage: str | None
    progress: int
    error_message: str | None
    retry_count: int
    result: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
