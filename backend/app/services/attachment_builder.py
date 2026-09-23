"""V3 Attachments builder (docs/v3-schema-manifest.md §5).

Primary source: a dedicated "SECTION J - LIST OF ATTACHMENTS" listing
parser (`build_attachments_from_section_j`) — this is the actual
enumerated attachment list (analogous to Section I's clause listing),
giving one clean, deduplicated row per real attachment rather than one row
per incidental narrative mention. Falls back to ATTACHMENT-category
`ClassifiedCandidate`s (narrative "attachment"/"exhibit"/"appendix" hits)
only when no Section J listing is found at all, since a scattered-mentions
fallback is strictly worse (confirmed: without the Section J parser, the
same J-1/J-4 items were captured 3-6x each from incidental prose mentions
elsewhere, instead of once each from the real list).
"""

from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_attachment import DocumentAttachment
from app.models.document_page import DocumentPage
from app.schemas.candidate_classification import ClassifiedCandidate

_REFERENCE_RE = re.compile(
    r"\b(Attachment|Exhibit|Appendix)\s+\(?([A-Za-z0-9.\-]+)\)?", re.IGNORECASE
)

_SECTION_J_HEADING_RE = re.compile(
    r"^\s*SECTION\s+J\b(?!.*\.{2,}\s*\d+\s*$)", re.IGNORECASE | re.MULTILINE
)
_J1_SUBHEADING_RE = re.compile(r"^\s*J\.1\b", re.IGNORECASE)
_J2_SUBHEADING_RE = re.compile(r"^\s*J\.2\b", re.IGNORECASE)
_ITEM_MARKER_RE = re.compile(r"^\s*(J(?:\.P)?-\d+)\b\s*(.*)$", re.IGNORECASE)
_SECTION_END_RE = re.compile(r"^\s*\(End of Section J\)", re.IGNORECASE)


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


def _find_section_j_page(pages: list[DocumentPage]) -> DocumentPage | None:
    for page in sorted(pages, key=lambda p: p.page_number):
        if _SECTION_J_HEADING_RE.search(page.final_text or ""):
            return page
    return None


def build_attachments_from_section_j(
    *, document: Document, pages: list[DocumentPage]
) -> list[DocumentAttachment] | None:
    """Returns None (caller should fall back) when no Section J listing is
    found; otherwise the complete, deduplicated attachment list."""

    page = _find_section_j_page(pages)
    if page is None:
        return None

    lines = (page.final_text or "").splitlines()
    rows: list[DocumentAttachment] = []
    current_ref: str | None = None
    current_title_parts: list[str] = []
    in_rfp_section = False

    def _flush(row_index: int) -> None:
        if current_ref is None:
            return
        title = " ".join(part.strip() for part in current_title_parts if part.strip())
        reserved = "reserved" in title.lower()
        if reserved:
            portfolio = "Reserved"
        elif in_rfp_section:
            portfolio = "No — RFP-only, excluded from executed contract"
        else:
            portfolio = "Yes"
        rows.append(
            DocumentAttachment(
                document_id=document.id,
                row_index=row_index,
                attachment_reference=current_ref,
                title_description=title or None,
                included_in_portfolio=portfolio,
                qa_status="Verified",
                confidence=0.9,
                evidence_json={
                    "page_number": page.page_number,
                    "source_text": f"{current_ref} {title}".strip(),
                    "reason_codes": ["section_j_listing"],
                },
            )
        )

    for line in lines:
        if _J1_SUBHEADING_RE.match(line):
            in_rfp_section = False
            continue
        if _J2_SUBHEADING_RE.match(line):
            _flush(len(rows))
            current_ref, current_title_parts = None, []
            in_rfp_section = True
            continue
        if _SECTION_END_RE.match(line):
            break

        match = _ITEM_MARKER_RE.match(line)
        if match:
            _flush(len(rows))
            current_ref = match.group(1).upper()
            current_title_parts = [match.group(2)]
            continue

        if current_ref is not None and line.strip():
            current_title_parts.append(line)

    _flush(len(rows))
    return rows


def build_attachments(
    *, document: Document, candidates: list[ClassifiedCandidate]
) -> list[DocumentAttachment]:
    """Narrative-mention fallback — used only when no Section J listing
    exists in the document (see build_attachments_from_section_j)."""

    rows: list[DocumentAttachment] = []
    seen: set[str] = set()

    for index, candidate in enumerate(candidates):
        if candidate.category != "ATTACHMENT":
            continue
        evidence = candidate.evidence or ""
        if not evidence.strip():
            continue
        reference, title = _reference_and_title(evidence)
        dedupe_key = reference.strip().lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

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
