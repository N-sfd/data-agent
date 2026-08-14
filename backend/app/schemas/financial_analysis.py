from typing import Any

from pydantic import BaseModel, Field


class FinancialAnalysisRequest(BaseModel):
    instruction: str = Field(
        min_length=3,
        max_length=2000,
    )

    page_start: int | None = Field(
        default=None,
        ge=1,
    )

    page_end: int | None = Field(
        default=None,
        ge=1,
    )


class FinancialTableResult(BaseModel):
    table_id: str
    page_number: int

    headers: list[str]
    rows: list[dict[str, Any]]

    confidence: float
    source_reference: str

    warnings: list[str] = Field(
        default_factory=list
    )


class FinancialAnalysisResponse(BaseModel):
    document_id: str
    instruction: str

    pages_used: list[int]

    tables: list[FinancialTableResult]

    status: str

    warnings: list[str] = Field(
        default_factory=list
    )