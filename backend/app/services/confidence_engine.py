"""Blends real extraction signals into an explainable confidence object."""

from __future__ import annotations

from typing import Literal

from app.models.document_page import DocumentPage
from app.schemas.extraction_intelligence import (
    ConfidenceDetail,
    ConfidenceSignals,
)

ConfidenceBand = Literal["high", "medium", "low"]

_BASE_CONFIDENCE_BY_METHOD: dict[str, float] = {
    "source_evidence": 0.90,
    "form_field": 0.82,
    "label_value": 0.72,
    "layout_proximity": 0.68,
    "regex": 0.70,
    "ai": 0.55,
}

_MAX_CORROBORATION_BONUS = 0.10
_CORROBORATION_BONUS_PER_OCCURRENCE = 0.03

_OCR_SUCCEEDED_PENALTY = 0.08
_OCR_FAILED_PENALTY = 0.25
_OCR_LOW_COVERAGE_PENALTY = 0.05
_LOW_TEXT_COVERAGE_THRESHOLD = 0.3
_SOURCE_GROUNDED_BONUS = 0.05
_VALIDATION_PASSED_BONUS = 0.05
_AMBIGUITY_PENALTY = 0.15
_EXACT_LABEL_BONUS = 0.05

_MIN_CONFIDENCE = 0.05
_MAX_CONFIDENCE = 0.99


def confidence_band(confidence: float) -> ConfidenceBand:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.60:
        return "medium"
    return "low"


def _label_proximity(
    *,
    method: str,
    match_exactness: float,
) -> Literal["strong", "moderate", "weak", "none"]:
    if method in {"source_evidence", "form_field"} and match_exactness >= 0.9:
        return "strong"
    if method == "label_value" or match_exactness >= 0.75:
        return "moderate"
    if method == "ai":
        return "weak"
    if match_exactness > 0:
        return "weak"
    return "none"


def explain_confidence(
    *,
    method: str,
    match_exactness: float = 1.0,
    occurrence_count: int = 1,
    page: DocumentPage | None = None,
    source_grounded: bool = True,
    validation_passed: bool = True,
    ambiguous_candidates: int = 0,
    exact_label_match: bool | None = None,
) -> ConfidenceDetail:
    """Return score + band + inspectable boolean/enum signals."""

    exact = (
        exact_label_match
        if exact_label_match is not None
        else method in {"source_evidence", "form_field", "label_value"}
        and match_exactness >= 0.95
    )
    native = bool(
        page is not None and not getattr(page, "requires_ocr", False)
    )
    ambiguity = ambiguous_candidates > 1
    ai_fallback = method == "ai"

    score = _BASE_CONFIDENCE_BY_METHOD.get(method, 0.60)
    score += (match_exactness - 1.0) * 0.15

    if exact:
        score += _EXACT_LABEL_BONUS

    if occurrence_count > 1:
        score += min(
            _MAX_CORROBORATION_BONUS,
            _CORROBORATION_BONUS_PER_OCCURRENCE * (occurrence_count - 1),
        )

    if page is not None and getattr(page, "requires_ocr", False):
        if not getattr(page, "ocr_succeeded", False):
            score -= _OCR_FAILED_PENALTY
        else:
            score -= _OCR_SUCCEEDED_PENALTY
            if (
                getattr(page, "text_coverage_ratio", None) or 0
            ) < _LOW_TEXT_COVERAGE_THRESHOLD:
                score -= _OCR_LOW_COVERAGE_PENALTY

    if source_grounded:
        score += _SOURCE_GROUNDED_BONUS
    if validation_passed:
        score += _VALIDATION_PASSED_BONUS
    if ambiguity:
        score -= _AMBIGUITY_PENALTY

    final = round(max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, score)), 2)
    signals = ConfidenceSignals(
        exact_label_match=exact,
        label_proximity=_label_proximity(
            method=method, match_exactness=match_exactness
        ),
        native_text=native,
        format_validation=validation_passed,
        source_grounded=source_grounded,
        corroborating_occurrences=max(0, occurrence_count),
        ambiguity=ambiguity,
        ai_fallback=ai_fallback,
    )
    return ConfidenceDetail(
        score=final,
        band=confidence_band(final),
        signals=signals,
    )


def compute_confidence(
    *,
    method: str,
    match_exactness: float = 1.0,
    occurrence_count: int = 1,
    page: DocumentPage | None = None,
    source_grounded: bool = True,
    validation_passed: bool = True,
    ambiguous_candidates: int = 0,
    exact_label_match: bool | None = None,
) -> float:
    return explain_confidence(
        method=method,
        match_exactness=match_exactness,
        occurrence_count=occurrence_count,
        page=page,
        source_grounded=source_grounded,
        validation_passed=validation_passed,
        ambiguous_candidates=ambiguous_candidates,
        exact_label_match=exact_label_match,
    ).score


def display_method(extraction_method: str, page: DocumentPage | None) -> str:
    if extraction_method == "ai":
        return "AI Fallback"
    if extraction_method == "manual":
        return "Manual"
    if page is not None and getattr(page, "requires_ocr", False):
        return "OCR"
    return "Native"
