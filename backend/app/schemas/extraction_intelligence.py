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


class ConfidenceDetail(BaseModel):
    score: float
    band: Literal["high", "medium", "low"]
    signals: ConfidenceSignals


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
