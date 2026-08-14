from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
