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
from app.models.document_page import DocumentPage
from app.models.document_performance_period import DocumentPerformancePeriod
from app.schemas.candidate_classification import ClassifiedCandidate

_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")
_RELATIVE_TIMING_RE = re.compile(
    r"\bwithin\s+\d+\s+(?:calendar\s+)?days?\b", re.IGNORECASE
)
_CLIN_RE = re.compile(r"\b\d{4,6}[A-Z]{0,2}\b")

# Quality-gate finding: a NARRATIVE region's captured text is a fixed-width
# line/paragraph fragment, not necessarily a complete sentence — the
# regression contract's own "period of performance" narrative mentions came
# through as arbitrary mid-sentence truncations (e.g. "will not be awarded
# a full ten year period of performance. Each award made after the
# initial"). Widening to the surrounding sentence(s) on the source page
# makes `requirement` an honest, complete quote instead of a fragment,
# without inventing any text beyond what the page actually says.
_CROSS_REFERENCE_RE = re.compile(
    r"^\s*See\s+Section\s+[A-Z0-9.]+", re.IGNORECASE
)


def _widen_to_sentence(evidence: str, page_text: str) -> str:
    if not page_text.strip():
        return evidence
    idx = page_text.find(evidence[:40])
    if idx == -1:
        return evidence
    start = max(0, page_text.rfind(".", 0, idx) + 1)
    end_search_from = idx + len(evidence)
    end = page_text.find(".", end_search_from)
    end = end + 1 if end != -1 else min(len(page_text), end_search_from + 200)
    widened = page_text[start:end].strip()
    return widened or evidence

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
    *,
    document: Document,
    candidates: list[ClassifiedCandidate],
    pages: list[DocumentPage] | None = None,
) -> list[DocumentPerformancePeriod]:
    pages_by_number = {p.page_number: (p.final_text or "") for p in (pages or [])}
    rows: list[DocumentPerformancePeriod] = []
    seen: set[str] = set()

    for index, candidate in enumerate(candidates):
        if candidate.category != "PERFORMANCE_DELIVERY":
            continue
        raw_evidence = candidate.evidence or ""
        if not raw_evidence.strip():
            continue
        page_text = pages_by_number.get(candidate.source_page, "")
        evidence = _widen_to_sentence(raw_evidence, page_text)
        dedupe_key = evidence.strip().lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        dates = _DATE_RE.findall(evidence)
        relative_timing = _RELATIVE_TIMING_RE.search(evidence)
        is_unresolved_cross_reference = bool(_CROSS_REFERENCE_RE.match(evidence))
        qa_status = (
            "Needs Review"
            if is_unresolved_cross_reference
            else ("Verified" if candidate.confidence >= 0.6 else "Needs Review")
        )
        reason_codes = list(candidate.reason_codes)
        if is_unresolved_cross_reference:
            # Points elsewhere in the document (e.g. "See Section F.3") for
            # the actual value rather than stating one itself — flagged so
            # a reviewer knows to cross-check rather than treating this row
            # as a resolved performance value.
            reason_codes.append("unresolved_cross_reference")

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
                    "reason_codes": reason_codes,
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
