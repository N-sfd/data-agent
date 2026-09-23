"""V3 Performance Delivery builder (docs/v3-schema-manifest.md §4).

Consumes PERFORMANCE_DELIVERY-category `ClassifiedCandidate`s (narrative
keyword hits from `candidate_router.route_page_regions`). Persists into the
extended `DocumentPerformancePeriod` table (the ground-truth sheet's merged
shape — `Record Type`/`CLIN`/`End/Timing`/`Location/Destination`/
`Requirement` columns added directly to it, per v3-implementation-plan.md
Phase 6's "merge only at export/query time, avoid a destructive migration"
recommendation). `DocumentDeliverySchedule` (dodaac/cage_code/ship-to
per-delivery-item detail) has no populating extraction logic yet — known
limitation, not silently dropped data (nothing currently produces it on
either the old or new pipeline).

`Record Type` is deliberately an open/free-text set, not an enum — the
ground truth and the regression contract both show values beyond any fixed
list (docs/v3-schema-manifest.md §4, docs/source-to-v3-mapping.md).
"""

from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_performance_period import DocumentPerformancePeriod
from app.schemas.candidate_classification import ClassifiedCandidate

_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")
_RELATIVE_TIMING_RE = re.compile(
    r"\bwithin\s+\d+\s+(?:calendar\s+)?days?\b", re.IGNORECASE
)
_CLIN_RE = re.compile(r"\b\d{4,6}[A-Z]{0,2}\b")

_RECORD_TYPE_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("period of performance",), "Period of Performance"),
    (("place of performance",), "Place of Performance"),
    (("fob",), "FOB"),
    (("commencement of work", "commencement"), "Commencement"),
    (("delivery date", "delivery location", "delivery schedule"), "Delivery"),
)


def _record_type(evidence: str) -> str:
    lowered = evidence.lower()
    for keywords, record_type in _RECORD_TYPE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return record_type
    return "Task Order Content"


def build_performance_delivery(
    *, document: Document, candidates: list[ClassifiedCandidate]
) -> list[DocumentPerformancePeriod]:
    rows: list[DocumentPerformancePeriod] = []
    seen: set[str] = set()

    for index, candidate in enumerate(candidates):
        if candidate.category != "PERFORMANCE_DELIVERY":
            continue
        evidence = candidate.evidence or ""
        if not evidence.strip():
            continue
        dedupe_key = evidence.strip().lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        dates = _DATE_RE.findall(evidence)
        relative_timing = _RELATIVE_TIMING_RE.search(evidence)
        qa_status = "Verified" if candidate.confidence >= 0.6 else "Needs Review"

        rows.append(
            DocumentPerformancePeriod(
                document_id=document.id,
                row_index=index,
                period_label=_record_type(evidence),
                start_date=dates[0] if dates else None,
                end_date=dates[1] if len(dates) > 1 else None,
                record_type=_record_type(evidence),
                clin=(_CLIN_RE.search(evidence).group(0) if _CLIN_RE.search(evidence) else None),
                end_timing=(
                    relative_timing.group(0)
                    if relative_timing
                    else (dates[1] if len(dates) > 1 else None)
                ),
                requirement=evidence[:500],
                qa_status=qa_status,
                confidence=candidate.confidence,
                evidence_json={
                    "page_number": candidate.source_page,
                    "source_text": evidence,
                    "reason_codes": candidate.reason_codes,
                },
            )
        )
    return rows


def persist_performance_delivery(
    *, database: Session, document_id: str, rows: list[DocumentPerformancePeriod]
) -> None:
    database.execute(
        delete(DocumentPerformancePeriod).where(
            DocumentPerformancePeriod.document_id == document_id
        )
    )
    for row in rows:
        database.add(row)
