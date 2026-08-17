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


class AIFieldResult(BaseModel):
    field_key: str

    value: str

    page_number: int = Field(
        ge=1
    )

    source_text: str

    confidence: float = Field(
        default=0.7,
        ge=0,
        le=1,
    )


class AIFieldExtractionResult(BaseModel):
    fields: list[AIFieldResult] = Field(
        default_factory=list
    )


class AIClauseResult(BaseModel):
    clause_type: str

    classification: str

    extracted_text: str

    value_summary: str = ""

    page_number: int = Field(
        ge=1
    )

    confidence: float = Field(
        default=0.7,
        ge=0,
        le=1,
    )


class AIClauseExtractionResult(BaseModel):
    clauses: list[AIClauseResult] = Field(
        default_factory=list
    )


class AISignatureResult(BaseModel):
    party_name: str

    signatory_name: str = ""

    signatory_title: str = ""

    signed: bool = False

    signature_date: str | None = None

    page_number: int = Field(
        ge=1
    )

    source_text: str

    confidence: float = Field(
        default=0.7,
        ge=0,
        le=1,
    )


class AISignatureExtractionResult(BaseModel):
    signatures: list[AISignatureResult] = Field(
        default_factory=list
    )
