from typing import Literal

from pydantic import BaseModel, Field

ExtractionType = Literal[
    "field",
    "table",
    "contact",
    "obligation",
    "clause",
    "signature",
    "custom",
]


class DetectedTarget(BaseModel):
    key: str
    label: str
    extraction_type: ExtractionType
    pages: list[int]
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    suggested_prompt: str | None = None
    columns: list[str] = Field(default_factory=list)
    discovery_method: str | None = None
    source_labels: list[str] = Field(default_factory=list)


class DetectedTable(BaseModel):
    key: str
    label: str
    pages: list[int]
    confidence: float
    suggested_prompt: str | None = None
    columns: list[str] = Field(default_factory=list)


class DetectedField(BaseModel):
    key: str
    label: str
    pages: list[int]


class ContentStats(BaseModel):
    tables: int
    dates: int
    currency_values: int
    organizations: int


class DetectionCounts(BaseModel):
    fields: int = 0
    tables: int = 0
    contacts: int = 0
    obligations: int = 0
    clauses: int = 0
    signatures: int = 0


class StructureDetectionResponse(BaseModel):
    document_id: str

    document_family: str
    document_family_label: str
    document_family_confidence: float = 0.0

    detected_fields: list[DetectedField]
    detected_tables: list[DetectedTable]
    detected_contacts: list[str]
    detected_obligations: list[str]

    detected_targets: list[DetectedTarget] = Field(default_factory=list)
    possible_targets: list[DetectedTarget] = Field(default_factory=list)

    content_stats: ContentStats
    counts: DetectionCounts = Field(default_factory=DetectionCounts)
