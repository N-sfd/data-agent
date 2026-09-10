from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.universal_extraction import SourceEvidence

CorrectionAction = Literal["edit", "verify", "reject"]


class TargetCorrectionCreate(BaseModel):
    action: CorrectionAction = "edit"
    original_value: Any = None
    corrected_value: Any = None
    evidence: SourceEvidence | None = None
    changed_by: str | None = None


class TargetCorrectionResponse(BaseModel):
    id: int
    document_id: str
    normalized_key: str
    action: CorrectionAction = "edit"
    original_value: Any = None
    corrected_value: Any = None
    evidence_snapshot: SourceEvidence | None = None
    changed_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
