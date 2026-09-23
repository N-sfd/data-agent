"""V3 Attachments builder (docs/v3-schema-manifest.md §5).

No existing extraction code anywhere (confirmed gap analysis, built from
scratch here). Consumes ATTACHMENT-category `ClassifiedCandidate`s
(narrative keyword hits — "attachment"/"exhibit"/"appendix" — from
`candidate_router.route_page_regions`). `Included in Portfolio?` is free
text, not boolean, per the ground-truth sheet's own convention.
"""

from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_attachment import DocumentAttachment
from app.schemas.candidate_classification import ClassifiedCandidate

_REFERENCE_RE = re.compile(
    r"\b(Attachment|Exhibit|Appendix)\s+\(?([A-Za-z0-9.\-]+)\)?", re.IGNORECASE
)


def _reference_and_title(evidence: str) -> tuple[str, str | None]:
    match = _REFERENCE_RE.search(evidence)
    if not match:
        return evidence[:80].strip(), None
    reference = match.group(0).strip()
    remainder = evidence[match.end():].strip(" -:.")
    return reference, (remainder[:300] or None)


def _included_in_portfolio(evidence: str) -> str:
    lowered = evidence.lower()
    if "reserved" in lowered:
        return "Reserved"
    if ("rfp" in lowered or "solicitation" in lowered) and (
        "not" in lowered or "exclud" in lowered
    ):
        return "No — RFP-only, excluded from executed contract"
    if "remain" in lowered:
        return "Yes"
    return "Needs Review — portfolio inclusion not stated explicitly"


def build_attachments(
    *, document: Document, candidates: list[ClassifiedCandidate]
) -> list[DocumentAttachment]:
    rows: list[DocumentAttachment] = []
    seen: set[str] = set()

    for index, candidate in enumerate(candidates):
        if candidate.category != "ATTACHMENT":
            continue
        evidence = candidate.evidence or ""
        if not evidence.strip():
            continue
        dedupe_key = evidence.strip().lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        reference, title = _reference_and_title(evidence)
        qa_status = "Verified" if candidate.confidence >= 0.6 else "Needs Review"

        rows.append(
            DocumentAttachment(
                document_id=document.id,
                row_index=index,
                attachment_reference=reference,
                title_description=title,
                included_in_portfolio=_included_in_portfolio(evidence),
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


def persist_attachments(
    *, database: Session, document_id: str, rows: list[DocumentAttachment]
) -> None:
    database.execute(
        delete(DocumentAttachment).where(DocumentAttachment.document_id == document_id)
    )
    for row in rows:
        database.add(row)
