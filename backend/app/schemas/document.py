from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExistingDocumentSummary(BaseModel):
    document_id: UUID
    original_filename: str
    size_bytes: int
    uploaded_at: datetime


class UploadedDocumentResponse(BaseModel):
    document_id: UUID
    original_filename: str
    status: str
    content_type: str
    size_bytes: int = Field(ge=1)
    checksum_sha256: str
    page_count: int = Field(ge=1)
    encrypted: bool
    uploaded_at: datetime
    message: str
    duplicate: bool = False
    existing_document: ExistingDocumentSummary | None = None
    pipeline_log: list[str] = Field(default_factory=list)
    approved_by: str | None = None
    approved_at: datetime | None = None


class ResolveDuplicateRequest(BaseModel):
    action: Literal["use_existing", "upload_anyway"]
    original_filename: str | None = None


class DocumentSummaryResponse(BaseModel):
    document_id: str
    original_filename: str
    document_type: str | None
    status: Literal["processing", "review_required", "completed"]
    confidence: float | None
    uploaded_at: datetime
    page_count: int
    fields_extracted: int
    last_updated: datetime


class DocumentSearchResponse(BaseModel):
    documents: list[DocumentSummaryResponse]
    total: int
