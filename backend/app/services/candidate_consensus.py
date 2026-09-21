"""Candidate consensus for scanned-field extraction.

Never silently invent or “correct” uncertain IDs/dates/amounts. When
candidates disagree without a strong winner, mark Needs Review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.label_rejection import reject_as_field_value


Decision = Literal["auto_select", "needs_review", "reject"]


@dataclass(frozen=True)
class ExtractionCandidate:
    value: str
    raw_ocr: str
    method: str
    ocr_confidence: float | None = None
    layout_confidence: float | None = None
    source_page: int | None = None
    source_bbox: list[float] | None = None
    notes: str | None = None


@dataclass
class ConsensusResult:
    decision: Decision
    selected: ExtractionCandidate | None
    normalized_value: str | None
    review_status: Literal["pending", "needs_review", "ready"]
    reason: str
    candidates: list[ExtractionCandidate] = field(default_factory=list)

    def evidence_payload(self, *, field_key: str) -> dict[str, Any]:
        selected = self.selected
        return {
            "field": field_key,
            "value": self.normalized_value,
            "raw_ocr": selected.raw_ocr if selected else None,
            "normalized_value": self.normalized_value,
            "source_page": selected.source_page if selected else None,
            "source_bbox": selected.source_bbox if selected else None,
            "extraction_method": selected.method if selected else None,
            "ocr_confidence": selected.ocr_confidence if selected else None,
            "layout_confidence": (
                selected.layout_confidence if selected else None
            ),
            "validation_status": None,
            "review_status": self.review_status,
            "consensus_decision": self.decision,
            "consensus_reason": self.reason,
            "candidate_count": len(self.candidates),
            "candidates": [
                {
                    "value": item.value,
                    "method": item.method,
                    "ocr_confidence": item.ocr_confidence,
                    "layout_confidence": item.layout_confidence,
                }
                for item in self.candidates[:8]
            ],
        }


def _normalize(value: str) -> str:
    return " ".join(value.strip().split())


def resolve_candidates(
    candidates: list[ExtractionCandidate],
    *,
    value_type: str | None = None,
    known_labels: frozenset[str] | None = None,
    field_key: str | None = None,
    min_auto_ocr_confidence: float = 0.85,
    min_auto_layout_confidence: float = 0.70,
) -> ConsensusResult:
    usable: list[ExtractionCandidate] = []
    for candidate in candidates:
        value = _normalize(candidate.value or "")
        if not value:
            continue
        rejection = reject_as_field_value(
            value,
            value_type=value_type,
            known_labels=known_labels,
            field_key=field_key,
        )
        if rejection:
            continue
        usable.append(
            ExtractionCandidate(
                value=value,
                raw_ocr=candidate.raw_ocr or value,
                method=candidate.method,
                ocr_confidence=candidate.ocr_confidence,
                layout_confidence=candidate.layout_confidence,
                source_page=candidate.source_page,
                source_bbox=candidate.source_bbox,
                notes=candidate.notes,
            )
        )

    if not usable:
        return ConsensusResult(
            decision="reject",
            selected=None,
            normalized_value=None,
            review_status="needs_review",
            reason="no_acceptable_candidates",
            candidates=list(candidates),
        )

    # Group by normalized value (case-insensitive for IDs keep original).
    groups: dict[str, list[ExtractionCandidate]] = {}
    for item in usable:
        key = item.value.upper() if value_type in {
            "identifier",
            "id",
            "contract_number",
            "solicitation_number",
        } else item.value.lower()
        groups.setdefault(key, []).append(item)

    if len(groups) == 1:
        winner = usable[0]
        ocr_ok = (
            winner.ocr_confidence is None
            or winner.ocr_confidence >= min_auto_ocr_confidence
        )
        layout_ok = (
            winner.layout_confidence is None
            or winner.layout_confidence >= min_auto_layout_confidence
        )
        if ocr_ok and layout_ok:
            return ConsensusResult(
                decision="auto_select",
                selected=winner,
                normalized_value=winner.value,
                review_status="ready",
                reason="unanimous_candidates",
                candidates=usable,
            )
        return ConsensusResult(
            decision="needs_review",
            selected=winner,
            normalized_value=winner.value,
            review_status="needs_review",
            reason="unanimous_but_low_confidence",
            candidates=usable,
        )

    # Disagreement: never invent a “most plausible” ID.
    return ConsensusResult(
        decision="needs_review",
        selected=None,
        normalized_value=None,
        review_status="needs_review",
        reason="conflicting_candidates",
        candidates=usable,
    )
