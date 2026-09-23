"""V3 QA Review builder (docs/v3-schema-manifest.md §10).

Per v3-implementation-plan.md decision #3: reproduces the ground truth's
category-level checklist shape exactly — one row per dataset area,
PASS/REVIEW + Details + Action — computed LAST, from each dataset's own
already-persisted `qa_status` values. Not a granular per-record issue log
(that stays internal, on each dataset row's own `qa_status`/`evidence_json`,
for the UI's source-review drawer).
"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_attachment import DocumentAttachment
from app.models.document_clause_reference import DocumentClauseReference
from app.models.document_contract_summary import DocumentContractSummary
from app.models.document_funding_line import DocumentFundingLine
from app.models.document_line_item import DocumentLineItem
from app.models.document_performance_period import DocumentPerformancePeriod
from app.models.document_qa_review import DocumentQaReview

_VERIFIED_STATUSES = frozenset({"verified", "pass"})


def _is_verified(qa_status: str | None) -> bool:
    if not qa_status:
        return False
    return any(token in qa_status.lower() for token in _VERIFIED_STATUSES)


def _needs_review_count(qa_statuses: list[str | None]) -> int:
    return sum(1 for status in qa_statuses if not _is_verified(status))


def _row(
    qa_check: str, qa_statuses: list[str | None], *, row_index: int, empty_ok: bool = False
) -> DocumentQaReview:
    total = len(qa_statuses)
    needs_review = _needs_review_count(qa_statuses)

    if total == 0:
        result = "PASS" if empty_ok else "REVIEW"
        details = "No records extracted for this dataset."
        action = "None" if empty_ok else "Confirm whether this contract legitimately has none."
    elif needs_review == 0:
        result = "PASS"
        details = f"{total} record(s), all Verified."
        action = "None"
    else:
        result = "REVIEW"
        details = f"{needs_review} of {total} record(s) flagged Needs Review."
        action = "Review flagged records against source evidence."

    return DocumentQaReview(
        document_id="",  # set by caller
        row_index=row_index,
        qa_check=qa_check,
        result=result,
        details=details,
        action=action,
    )


def build_qa_review(
    *,
    document: Document,
    contract_summary: DocumentContractSummary | None,
    clins: list[DocumentLineItem],
    funding: list[DocumentFundingLine],
    performance_delivery: list[DocumentPerformancePeriod],
    attachments: list[DocumentAttachment],
    clause_references: list[DocumentClauseReference],
) -> list[DocumentQaReview]:
    clauses = [
        row
        for row in clause_references
        if row.clause_family in ("FAR", "GSAR") and row.citation_context == "listing"
    ]
    dfars = [row for row in clause_references if row.clause_family == "DFARS"]
    far_references = [row for row in clause_references if row.citation_context == "incidental"]

    checks = [
        (
            "Contract Summary",
            [contract_summary.qa_status] if contract_summary else [],
        ),
        ("CLINs", [row.qa_status for row in clins]),
        ("Funding", [row.qa_status for row in funding]),
        ("Performance / Delivery", [row.qa_status for row in performance_delivery]),
        ("Attachments", [row.qa_status for row in attachments]),
        ("Clauses", [row.qa_status for row in clauses]),
        ("FAR References", [row.qa_status for row in far_references]),
        ("DFARS", [row.qa_status for row in dfars]),
    ]

    rows: list[DocumentQaReview] = []
    for index, (qa_check, qa_statuses) in enumerate(checks):
        # Funding/Attachments/FAR References/DFARS legitimately can be
        # empty for a given contract (e.g. a base IDIQ award with no
        # obligated funds) — an empty dataset there is not itself a defect.
        empty_ok = qa_check in ("Funding", "Attachments", "FAR References", "DFARS")
        row = _row(qa_check, qa_statuses, row_index=index, empty_ok=empty_ok)
        row.document_id = document.id
        rows.append(row)

    return rows


def persist_qa_review(
    *, database: Session, document_id: str, rows: list[DocumentQaReview]
) -> None:
    database.execute(
        delete(DocumentQaReview).where(DocumentQaReview.document_id == document_id)
    )
    for row in rows:
        database.add(row)
