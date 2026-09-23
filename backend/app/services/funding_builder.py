"""V3 Funding builder (docs/v3-schema-manifest.md §3).

Consumes FUNDING-category `ClassifiedCandidate`s (narrative or table-row
hits from `candidate_router.route_page_regions`, already deduplicated
against CLIN candidates covering the same source line via
`deduplicate_clin_funding_overlap`). Per v3-implementation-plan.md decision
#4, a funding-requirement narrative row (e.g. "funds obligated only at
task-order issuance") is a legitimate Funding-sheet record, not something to
exclude — it is tagged via `Funding Level`, never silently dropped.
"""

from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_funding_line import DocumentFundingLine
from app.schemas.candidate_classification import ClassifiedCandidate

_AMOUNT_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")
_CLIN_RE = re.compile(r"\b\d{4,6}[A-Z]{0,2}\b")
_PURCHASE_REQUEST_RE = re.compile(r"\bPR[- ]?\d[\w-]{4,}\b", re.IGNORECASE)
_ACRN_RE = re.compile(r"\b[A-Z]{2}\d{2}\b")

_TASK_ORDER_KEYWORDS = ("task order",)
_MINIMUM_GUARANTEE_KEYWORDS = ("minimum guarantee",)


def _funding_level(evidence: str) -> str:
    lowered = evidence.lower()
    if any(keyword in lowered for keyword in _TASK_ORDER_KEYWORDS):
        return "Task Orders"
    if any(keyword in lowered for keyword in _MINIMUM_GUARANTEE_KEYWORDS):
        return "Minimum Guarantee"
    return "Basic IDIQ"


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def build_funding_lines(
    *, document: Document, candidates: list[ClassifiedCandidate]
) -> list[DocumentFundingLine]:
    rows: list[DocumentFundingLine] = []
    seen: set[str] = set()

    for index, candidate in enumerate(candidates):
        if candidate.category != "FUNDING":
            continue
        evidence = candidate.evidence or ""
        if not evidence.strip():
            continue
        dedupe_key = evidence.strip().lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        amount_text = _first_match(_AMOUNT_RE, evidence)
        amount = (
            float(amount_text.replace("$", "").replace(",", ""))
            if amount_text
            else None
        )
        qa_status = "Verified" if candidate.confidence >= 0.7 else "Needs Review"

        rows.append(
            DocumentFundingLine(
                document_id=document.id,
                row_index=index,
                acrn=_first_match(_ACRN_RE, evidence),
                amount=amount,
                funding_level=_funding_level(evidence),
                clin=_first_match(_CLIN_RE, evidence),
                funding_status=evidence[:500],
                purchase_request=_first_match(_PURCHASE_REQUEST_RE, evidence),
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


def persist_funding_lines(
    *, database: Session, document_id: str, rows: list[DocumentFundingLine]
) -> None:
    database.execute(
        delete(DocumentFundingLine).where(
            DocumentFundingLine.document_id == document_id
        )
    )
    for row in rows:
        database.add(row)
