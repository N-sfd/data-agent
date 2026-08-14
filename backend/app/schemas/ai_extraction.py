from typing import Any

from pydantic import BaseModel, Field


class AIExtractedValue(BaseModel):
    label: str

    value: Any

    value_type: str = "text"

    page_number: int = Field(
        ge=1
    )

    source_text: str

    confidence: float = Field(
        default=0.80,
        ge=0,
        le=1,
    )


class AIExtractionResult(BaseModel):
    answer: str | None = None

    values: list[AIExtractedValue] = Field(
        default_factory=list
    )

    unresolved: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )
