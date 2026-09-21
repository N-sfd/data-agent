"""Inspectable retrieval, confidence, and validation objects for extraction."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CandidatePageScore(BaseModel):
    page: int
    score: float


class RetrievalTrace(BaseModel):
    target_key: str
    candidate_pages: list[CandidatePageScore] = Field(default_factory=list)
    selected_pages: list[int] = Field(default_factory=list)
    deterministic_status: Literal[
        "resolved", "ambiguous", "unresolved", "not_attempted"
    ] = "not_attempted"
    ai_fallback_required: bool = False


class ConfidenceSignals(BaseModel):
    exact_label_match: bool = False
    label_proximity: Literal["strong", "moderate", "weak", "none"] = "none"
    native_text: bool = False
    format_validation: bool = False
    source_grounded: bool = False
    corroborating_occurrences: int = 0
    ambiguity: bool = False
    ai_fallback: bool = False


class ConfidenceComponents(BaseModel):
    """Separated confidence facets for auditability.

    OCR confidence ≠ extraction correctness. A validation-failed value
    must never surface a high *final* score even if OCR was sure.
    """

    ocr: float | None = None
    extraction: float | None = None
    validation: float | None = None
    final: float


class ConfidenceDetail(BaseModel):
    score: float
    band: Literal["high", "medium", "low"]
    signals: ConfidenceSignals
    components: ConfidenceComponents | None = None


class FieldEvidence(BaseModel):
    """Internal multi-evidence payload for a scalar extraction."""

    field: str
    value: str | None = None
    raw_ocr: str | None = None
    normalized_value: str | None = None
    source_page: int | None = None
    source_bbox: list[float] | None = None
    extraction_method: str | None = None
    ocr_confidence: float | None = None
    layout_confidence: float | None = None
    validation_status: str | None = None
    review_status: str | None = None
    confidence_components: ConfidenceComponents | None = None


class ValidationCheck(BaseModel):
    type: str
    status: Literal["passed", "failed", "skipped"] = "passed"
    detail: str | None = None


class ValidationResult(BaseModel):
    status: Literal["passed", "failed", "skipped"] = "passed"
    checks: list[ValidationCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def confidence_detail_to_legacy_signals(
    detail: ConfidenceDetail,
) -> list[dict[str, Any]]:
    """Keep list-shaped signals for older UI consumers."""

    signals = detail.signals
    return [
        {"signal": key, "value": value}
        for key, value in signals.model_dump().items()
    ]
