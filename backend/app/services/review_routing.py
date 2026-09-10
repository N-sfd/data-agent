"""Automatic review routing from extraction intelligence signals.

Does not invent new durable status values beyond the existing
pending/accepted/edited/rejected/unknown set. Fresh extracts stay
``pending`` (needs human governance) unless auto-accept is enabled for
clean high-confidence fields. Reasons are persisted for the Review Queue.
"""

from __future__ import annotations

from typing import Any, Literal

from app.schemas.document_target import ScalarTargetResult

ReviewDecisionStatus = Literal["needs_review", "ready_to_accept"]
ReviewPriority = Literal["high", "medium", "low"]

REASON_LOW_CONFIDENCE = "low_confidence"
REASON_VALIDATION_FAILED = "validation_failed"
REASON_NOT_SOURCE_GROUNDED = "not_source_grounded"
REASON_AMBIGUOUS = "ambiguous_candidates"
REASON_AI_ESCALATION = "ai_escalation"
REASON_UNRESOLVED_METHOD = "unresolved_or_weak_method"
REASON_EXTRACTION_DIFFERS = "extraction_differs_from_reviewed"


def decide_review_for_scalar(
    scalar: ScalarTargetResult,
    *,
    auto_accept_high_confidence: bool = False,
) -> dict[str, Any]:
    """Return a review_decision dict stored on evidence_json."""

    reasons: list[str] = []

    band = (scalar.confidence_band or "medium").lower()
    if band == "low" or (scalar.confidence is not None and scalar.confidence < 0.6):
        reasons.append(REASON_LOW_CONFIDENCE)

    validation = scalar.validation
    if validation is not None and validation.status == "failed":
        reasons.append(REASON_VALIDATION_FAILED)
    elif scalar.validation_status == "failed":
        reasons.append(REASON_VALIDATION_FAILED)

    if not scalar.verified:
        reasons.append(REASON_NOT_SOURCE_GROUNDED)

    retrieval = scalar.retrieval
    if retrieval is not None:
        if retrieval.deterministic_status == "ambiguous":
            reasons.append(REASON_AMBIGUOUS)
        if retrieval.ai_fallback_required or scalar.extraction_method == "ai":
            reasons.append(REASON_AI_ESCALATION)

    detail = scalar.confidence_detail
    if detail is not None and detail.signals.ambiguity:
        if REASON_AMBIGUOUS not in reasons:
            reasons.append(REASON_AMBIGUOUS)
    if detail is not None and detail.signals.ai_fallback:
        if REASON_AI_ESCALATION not in reasons:
            reasons.append(REASON_AI_ESCALATION)

    if not reasons and band == "medium":
        # Medium stays in queue for spot-check but is "ready_to_accept".
        decision_status: ReviewDecisionStatus = "ready_to_accept"
        priority: ReviewPriority = "medium"
    elif not reasons and band == "high":
        decision_status = "ready_to_accept"
        priority = "high"
    else:
        decision_status = "needs_review"
        if (
            REASON_VALIDATION_FAILED in reasons
            or REASON_AMBIGUOUS in reasons
            or band == "low"
        ):
            priority = "low"
        elif REASON_AI_ESCALATION in reasons:
            priority = "medium"
        else:
            priority = "medium"

    review_status = "pending"
    if (
        auto_accept_high_confidence
        and decision_status == "ready_to_accept"
        and priority == "high"
        and scalar.verified
    ):
        review_status = "accepted"

    return {
        "status": decision_status,
        "priority": priority,
        "reasons": reasons,
        "review_status": review_status,
    }


def human_reason_labels(reasons: list[str]) -> list[str]:
    labels = {
        REASON_LOW_CONFIDENCE: "Low confidence",
        REASON_VALIDATION_FAILED: "Validation failed",
        REASON_NOT_SOURCE_GROUNDED: "Not source-grounded",
        REASON_AMBIGUOUS: "Ambiguous candidates",
        REASON_AI_ESCALATION: "AI escalation",
        REASON_UNRESOLVED_METHOD: "Weak extraction method",
        REASON_EXTRACTION_DIFFERS: "New extraction differs from reviewed value",
    }
    return [labels.get(reason, reason) for reason in reasons]
