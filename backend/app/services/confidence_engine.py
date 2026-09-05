"""Blends real extraction signals into a single confidence score.

Every extraction path in target_extraction_service.py used to assign
confidence as either a flat per-method constant, a floor-clamped
discovery-time score, or (for AI results) whatever number the model
itself claimed. None of that reflects the signals the spec calls for:
label/match exactness, corroboration across the document, and source
page quality (native text vs. OCR). This module is the single place
that turns those signals into a score, so "confidence" means something
inspectable rather than an arbitrary percentage.
"""

from typing import Literal

from app.models.document_page import DocumentPage

ConfidenceBand = Literal["high", "medium", "low"]

# Reflects each mechanism's inherent reliability before any per-instance
# adjustment. source_evidence requires both a strict "label: value"
# pattern match at discovery time AND a passing validate_source_value
# grounding check, so a clean hit on native text lands in the "high"
# band without needing extra corroboration. label_value is a looser
# generic label scan with no discovery-time corroboration, so it starts
# in "medium" territory. AI starts lowest because it's an interpretive
# fallback rather than a pattern match.
_BASE_CONFIDENCE_BY_METHOD: dict[str, float] = {
    "source_evidence": 0.90,
    "form_field": 0.82,
    "label_value": 0.72,
    "ai": 0.55,
}

_MAX_CORROBORATION_BONUS = 0.10
_CORROBORATION_BONUS_PER_OCCURRENCE = 0.03

_OCR_SUCCEEDED_PENALTY = 0.08
_OCR_FAILED_PENALTY = 0.25
_OCR_LOW_COVERAGE_PENALTY = 0.05
_LOW_TEXT_COVERAGE_THRESHOLD = 0.3

_MIN_CONFIDENCE = 0.05
_MAX_CONFIDENCE = 0.99


def compute_confidence(
    *,
    method: str,
    match_exactness: float = 1.0,
    occurrence_count: int = 1,
    page: DocumentPage | None = None,
) -> float:
    """Blend method reliability, match quality, corroboration, and
    source page quality into a single 0-1 confidence score."""

    score = _BASE_CONFIDENCE_BY_METHOD.get(method, 0.60)

    # A fuzzy or partial match pulls the score down from the method's
    # base rate; an exact match (1.0) leaves it unchanged.
    score += (match_exactness - 1.0) * 0.15

    if occurrence_count > 1:
        score += min(
            _MAX_CORROBORATION_BONUS,
            _CORROBORATION_BONUS_PER_OCCURRENCE * (occurrence_count - 1),
        )

    # getattr with defaults: some callers pass lightweight page-like
    # fakes (e.g. tests) that don't carry every DocumentPage column.
    if page is not None and getattr(page, "requires_ocr", False):
        if not getattr(page, "ocr_succeeded", False):
            score -= _OCR_FAILED_PENALTY
        else:
            score -= _OCR_SUCCEEDED_PENALTY
            if (
                getattr(page, "text_coverage_ratio", None) or 0
            ) < _LOW_TEXT_COVERAGE_THRESHOLD:
                score -= _OCR_LOW_COVERAGE_PENALTY

    return round(max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, score)), 2)


def confidence_band(confidence: float) -> ConfidenceBand:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.60:
        return "medium"
    return "low"


def display_method(extraction_method: str, page: DocumentPage | None) -> str:
    """Map internal extraction_method values to the "Native / OCR / AI
    Fallback / Manual" vocabulary the extraction workspace shows."""

    if extraction_method == "ai":
        return "AI Fallback"

    if extraction_method == "manual":
        return "Manual"

    if page is not None and getattr(page, "requires_ocr", False):
        return "OCR"

    return "Native"
