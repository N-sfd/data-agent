from typing import Any, Literal

from pydantic import BaseModel, Field


class UniversalExtractionRequest(BaseModel):
    instruction: str = Field(
        min_length=2,
        max_length=4000,
    )

    page_start: int | None = Field(
        default=None,
        ge=1,
    )

    page_end: int | None = Field(
        default=None,
        ge=1,
    )

    max_pages: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    use_ai_fallback: bool = True


class SourceEvidence(BaseModel):
    page_number: int
    source_text: str
    source_reference: str

    section: str | None = None

    block_index: int | None = None

    x0: float | None = None
    y0: float | None = None
    x1: float | None = None
    y1: float | None = None


class ExtractedValue(BaseModel):
    label: str
    value: Any

    value_type: Literal[
        "text",
        "number",
        "money",
        "date",
        "email",
        "phone",
        "address",
        "identifier",
        "boolean",
        "list",
        "object",
    ] = "text"

    normalized_value: Any | None = None

    confidence: float = Field(
        default=0.8,
        ge=0,
        le=1,
    )

    extraction_method: Literal[
        "form_field",
        "regex",
        "label_value",
        "table",
        "ai",
    ]

    evidence: SourceEvidence

    verified: bool = False


class ExtractedTable(BaseModel):
    table_id: str

    title: str | None = None

    headers: list[str]

    rows: list[dict[str, Any]]

    page_number: int

    confidence: float = Field(
        ge=0,
        le=1,
    )

    source_reference: str


class UniversalExtractionResponse(BaseModel):
    document_id: str

    instruction: str

    intent: str

    answer: str | None = None

    values: list[ExtractedValue]

    tables: list[ExtractedTable]

    pages_used: list[int]

    unresolved_requests: list[str]

    warnings: list[str]


class AIExtractedValue(BaseModel):
    """Structured value returned by the AI fallback provider."""

    label: str
    value: Any

    page_number: int = Field(ge=1)

    source_text: str = Field(min_length=1)


class AIExtractionPayload(BaseModel):
    """
    Contract for AI fallback responses.

    Results without value, page_number, and source_text
    must be rejected before they enter the pipeline.
    """

    answer: str | None = None

    values: list[AIExtractedValue] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )
