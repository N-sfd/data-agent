from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.universal_extraction import SourceEvidence

TargetType = Literal[
    "field",
    "table",
    "section",
    "contact",
    "date",
    "amount",
    "identifier",
    "clause",
    "obligation",
    "signature",
    "custom",
]

TargetSource = Literal["detected", "template", "custom"]


class DocumentTarget(BaseModel):
    id: str
    key: str
    label: str
    target_type: TargetType
    page_numbers: list[int] = Field(default_factory=list)
    confidence: float
    source_examples: list[str] = Field(default_factory=list)
    parent_section: str | None = None
    columns: list[str] = Field(default_factory=list)
    occurrence_count: int = 1
    suggested_instruction: str | None = None
    source: TargetSource = "detected"


class DiscoverSchemaResponse(BaseModel):
    document_id: str
    document_family: str
    document_family_label: str
    document_family_confidence: float
    targets: list[DocumentTarget] = Field(default_factory=list)
    counts_by_type: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime


class ExtractTargetsRequest(BaseModel):
    target_ids: list[str] = Field(min_length=1, max_length=50)
    use_ai_fallback: bool = True


class CreateCustomTargetRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    target_type: TargetType = "custom"


class RenameCustomTargetRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)


class ScalarTargetResult(BaseModel):
    target: str
    normalized_key: str
    value: Any
    page: int
    confidence: float
    confidence_band: Literal["high", "medium", "low"] = "medium"
    verified: bool
    extraction_method: str
    display_method: str = ""
    evidence: SourceEvidence


class TableTargetResult(BaseModel):
    target: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)


class ExtractTargetsResponse(BaseModel):
    document_id: str
    scalars: list[ScalarTargetResult] = Field(default_factory=list)
    tables: list[TableTargetResult] = Field(default_factory=list)
    unresolved_targets: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
