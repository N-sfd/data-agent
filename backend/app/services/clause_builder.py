"""V3 Clauses / FAR References / DFARS builder (docs/v3-schema-manifest.md
§6-8, docs/far-master-schema-manifest.md).

One shared table (`document_clause_references`), split into three V3
sheets by two columns, never by three separate tables:
  - `clause_family` ("FAR" | "DFARS" | "GSAR")
  - `citation_context` ("listing" | "incidental")

Sheet                V3 export query
-----                ---------------
Clauses              clause_family in (FAR, GSAR) AND citation_context == listing
DFARS                clause_family == DFARS  (regardless of context — V3 has
                      no separate "DFARS incidental reference" sheet; decision
                      documented in v3-implementation-plan.md Phase 4)
FAR References       citation_context == incidental

FAR Master enrichment (far-master-schema-manifest.md's governing rule:
"FAR Master must never determine that a clause exists in a contract — contract
evidence determines presence") applies ONLY to FAR-family, listing-context
rows: DFARS/GSAR have no master reference file, so those rows are
`Verified` from contract evidence alone, matching the ground truth.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_clause_reference import DocumentClauseReference
from app.models.far_master_clause import FarMasterClause
from app.schemas.candidate_classification import ClassifiedCandidate


def _citation_context_for(candidate: ClassifiedCandidate) -> str:
    return "incidental" if candidate.category == "FAR_REFERENCE" else "listing"


def _enrich_far(
    *, clause_number: str, title: str | None, effective_date: str | None,
    far_master_by_number: dict[str, FarMasterClause],
) -> tuple[str, str]:
    """Returns (far_master_match_status, qa_status)."""

    master = far_master_by_number.get(clause_number)
    if master is None:
        return "not_found", "Needs Review"
    if master.record_type != "Clause":
        return "record_type_mismatch", "Needs Review"

    title_matches = True
    if title and master.clause_title:
        title_matches = title.strip().lower() == master.clause_title.strip().lower()
    date_matches = True
    if effective_date and master.effective_date:
        date_matches = (
            effective_date.strip().lower() == master.effective_date.strip().lower()
        )

    if not title_matches:
        return "title_mismatch", "Needs Review"
    if not date_matches:
        return "date_mismatch", "Needs Review"
    return "matched", "Verified"


def build_clause_references(
    *,
    database: Session,
    document: Document,
    candidates: list[ClassifiedCandidate],
) -> list[DocumentClauseReference]:
    far_candidates = [
        c
        for c in candidates
        if c.category in ("CLAUSE", "DFARS", "FAR_REFERENCE") and c.clause_number
    ]
    far_numbers = {c.clause_number for c in far_candidates if c.regulation == "FAR"}
    far_master_by_number: dict[str, FarMasterClause] = {}
    if far_numbers:
        master_rows = database.scalars(
            select(FarMasterClause).where(FarMasterClause.far_number.in_(far_numbers))
        )
        far_master_by_number = {row.far_number: row for row in master_rows}

    rows: list[DocumentClauseReference] = []
    seen: set[tuple[str, str]] = set()

    for index, candidate in enumerate(far_candidates):
        regulation = candidate.regulation or "FAR"
        dedupe_key = (regulation, candidate.clause_number)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        context = _citation_context_for(candidate)
        title = candidate.value

        if regulation == "FAR":
            far_master_match_status, qa_status = _enrich_far(
                clause_number=candidate.clause_number,
                title=title,
                effective_date=None,
                far_master_by_number=far_master_by_number,
            )
        else:
            # DFARS/GSAR: no master reference file (confirmed, far-master-
            # schema-manifest.md) — accepted from contract evidence alone,
            # same as the ground truth's own DFARS sheet.
            far_master_match_status = "not_applicable"
            qa_status = "Verified" if candidate.confidence >= 0.6 else "Needs Review"

        rows.append(
            DocumentClauseReference(
                document_id=document.id,
                row_index=index,
                clause_family=regulation,
                citation_context=context,
                clause_number=candidate.clause_number,
                title=title or "",
                incorporation_type=(
                    "Incorporated by Reference" if context == "listing" else None
                ),
                reference_type=("Narrative reference" if context == "incidental" else None),
                subject_context=(candidate.evidence if context == "incidental" else None),
                contract_clause=("No" if context == "incidental" else None),
                far_master_match_status=far_master_match_status,
                qa_status=qa_status,
                confidence=candidate.confidence,
                evidence_json={
                    "page_number": candidate.source_page,
                    "source_text": candidate.evidence,
                    "reason_codes": candidate.reason_codes,
                },
            )
        )

    return rows


def persist_clause_references(
    *, database: Session, document_id: str, rows: list[DocumentClauseReference]
) -> None:
    database.execute(
        delete(DocumentClauseReference).where(
            DocumentClauseReference.document_id == document_id
        )
    )
    for row in rows:
        database.add(row)
