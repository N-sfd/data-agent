"""Runs the full V3 extraction pipeline for one document and persists every
dataset in a single transaction. This is the one function the extraction
job (and the standalone regression script) calls — see
docs/v3-implementation-plan.md's architecture diagram.

    classify_document()  (v3_pipeline.py — structure_classifier + candidate_router)
        -> ClassifiedCandidate list + raw ClauseCitation/ParsedClinRow lists
    -> per-dataset builders (this module)
    -> persisted V3 tables (idempotent delete-then-insert per document)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.all_fields_builder import build_all_fields, persist_all_fields
from app.services.attachment_builder import (
    build_attachments,
    build_attachments_from_section_j,
    persist_attachments,
)
from app.services.clause_builder import build_clause_references, persist_clause_references
from app.services.clin_builder import build_clins, is_funding_shaped_row, persist_clins
from app.services.contract_summary_builder import (
    build_contract_summary,
    persist_contract_summary,
)
from app.services.funding_builder import (
    build_funding_lines,
    build_funding_lines_from_pricing_schedule_rows,
    persist_funding_lines,
)
from app.services.performance_delivery_builder import (
    build_performance_delivery,
    persist_performance_delivery,
)
from app.services.qa_review_builder import build_qa_review, persist_qa_review
from app.services.v3_pipeline import classify_document


@dataclass
class V3ExtractionSummary:
    candidate_count: int
    all_fields_count: int
    clin_count: int
    funding_count: int
    performance_delivery_count: int
    attachment_count: int
    clause_reference_count: int
    pages_classified: int
    pages_with_geometry: int
    warnings: list[str] = field(default_factory=list)


def run_and_persist_v3_extraction(
    *, database: Session, document: Document, pages: list[DocumentPage]
) -> V3ExtractionSummary:
    classification = classify_document(document=document, pages=pages)
    candidates = classification.candidates

    all_fields_rows = build_all_fields(document=document, candidates=candidates)
    clin_rows = build_clins(document=document, clin_rows=classification.clin_rows)
    funding_rows = build_funding_lines(document=document, candidates=candidates)
    funding_shaped_pricing_rows = [
        row for row in classification.clin_rows if is_funding_shaped_row(row)
    ]
    funding_rows.extend(
        build_funding_lines_from_pricing_schedule_rows(
            document=document,
            funding_shaped_rows=funding_shaped_pricing_rows,
            start_index=len(funding_rows),
        )
    )
    performance_rows = build_performance_delivery(document=document, candidates=candidates)
    attachment_rows = build_attachments_from_section_j(document=document, pages=pages)
    if attachment_rows is None:
        attachment_rows = build_attachments(document=document, candidates=candidates)
    clause_rows = build_clause_references(
        database=database, document=document, candidates=candidates
    )
    contract_summary = build_contract_summary(
        document=document, pages=pages, candidates=candidates
    )

    persist_all_fields(database=database, document_id=document.id, rows=all_fields_rows)
    persist_clins(database=database, document_id=document.id, rows=clin_rows)
    persist_funding_lines(database=database, document_id=document.id, rows=funding_rows)
    persist_performance_delivery(
        database=database, document_id=document.id, rows=performance_rows
    )
    persist_attachments(database=database, document_id=document.id, rows=attachment_rows)
    persist_clause_references(database=database, document_id=document.id, rows=clause_rows)
    persist_contract_summary(
        database=database, document_id=document.id, summary=contract_summary
    )

    qa_rows = build_qa_review(
        document=document,
        contract_summary=contract_summary,
        clins=clin_rows,
        funding=funding_rows,
        performance_delivery=performance_rows,
        attachments=attachment_rows,
        clause_references=clause_rows,
    )
    persist_qa_review(database=database, document_id=document.id, rows=qa_rows)

    database.commit()

    return V3ExtractionSummary(
        candidate_count=len(candidates),
        all_fields_count=len(all_fields_rows),
        clin_count=len(clin_rows),
        funding_count=len(funding_rows),
        performance_delivery_count=len(performance_rows),
        attachment_count=len(attachment_rows),
        clause_reference_count=len(clause_rows),
        pages_classified=classification.pages_classified,
        pages_with_geometry=classification.pages_with_geometry,
        warnings=classification.warnings,
    )
