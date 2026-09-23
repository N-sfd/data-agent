"""V3 classification pipeline orchestration.

Wires the previously-isolated structure_classifier / candidate_router layer
(proven correct against the regression contract by
backend/scripts/step1_regression_report.py and step2_regression_report.py,
but never called from production — see docs/v3-gap-analysis.md) into the
actual extraction job. This module owns exactly one job: turn a document's
already-extracted pages into a flat list of `ClassifiedCandidate`s. It does
not persist anything — see v3_persistence.py and the per-dataset builders
for that.

Geometry source per page, best available (line_model.best_available_lines):
  1. Live fitz.Page (native text/dict-mode) — the source PDF is reopened
     locally via the same `ensure_local_copy` helper the processing job
     already uses. This is NOT a re-OCR: it is a second, cheap read of the
     PDF's existing native text layer/positions.
  2. The OCR line layer already captured and persisted at processing time
     (`DocumentPage.ocr_layout_json`) — covers scanned pages with zero new
     OCR work.
  3. Nothing (empty) when neither is available for a page — that page still
     contributes clause citations and CLIN rows (both read `final_text`/
     `tables_json` directly from the persisted `DocumentPage`), just not
     geometry-based form-field pairing or heading/TOC detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.candidate_classification import ClassifiedCandidate
from app.services.candidate_router import (
    deduplicate_clin_funding_overlap,
    route_clause_citations,
    route_clin_rows,
    route_form_cell_associations,
    route_page_regions,
)
from app.services.clause_citation_scanner import ClauseCitation, scan_pages_for_clause_citations
from app.services.clin_block_detector import ParsedClinRow, parse_clin_rows
from app.services.document_storage import DocumentStorageError, ensure_local_copy
from app.services.form_cell_associator import associate_form_cells
from app.services.line_model import LogicalLine, best_available_lines
from app.services.structure_classifier import build_document_context, classify_page_regions


@dataclass
class V3ClassificationResult:
    candidates: list[ClassifiedCandidate]
    clause_citations: list[ClauseCitation]
    clin_rows: list[ParsedClinRow]
    pages_classified: int
    pages_with_geometry: int
    warnings: list[str] = field(default_factory=list)


def _open_source_pdf(document: Document):
    """Returns an opened fitz.Document, or None (with the reason folded
    into the caller's warnings) when the source file can't be restored."""

    try:
        import fitz
    except ImportError:
        return None, "PyMuPDF (fitz) is not available."

    settings = get_settings()
    try:
        file_path = ensure_local_copy(settings, stored_filename=document.stored_filename)
    except DocumentStorageError as exc:
        return None, f"source PDF unavailable ({exc})"

    try:
        return fitz.open(str(file_path)), None
    except Exception as exc:  # noqa: BLE001 - any fitz open failure
        return None, f"could not open source PDF ({exc})"


def classify_document(
    *, document: Document, pages: list[DocumentPage]
) -> V3ClassificationResult:
    """Synchronous and CPU-bound (PDF geometry parsing + regex/geometry
    classification, no network/AI calls) — callers should run this inside a
    threadpool, matching how `process_document_pages` is invoked."""

    warnings: list[str] = []

    if not pages:
        return V3ClassificationResult(
            candidates=[],
            clause_citations=[],
            clin_rows=[],
            pages_classified=0,
            pages_with_geometry=0,
            warnings=["No extracted pages available for V3 classification."],
        )

    fitz_doc, open_warning = _open_source_pdf(document)
    if open_warning:
        warnings.append(
            f"V3 classification: {open_warning} — falling back to the "
            "persisted OCR line layer / text-only classification for "
            "native-text pages on this document."
        )

    lines_by_page: dict[int, list[LogicalLine]] = {}
    pages_with_geometry = 0
    context_input: list[tuple[int, list[LogicalLine], float]] = []

    try:
        for page in pages:
            fitz_page = None
            if fitz_doc is not None and 0 <= page.page_number - 1 < fitz_doc.page_count:
                fitz_page = fitz_doc[page.page_number - 1]

            lines = best_available_lines(
                blocks=[],
                page_number=page.page_number,
                fitz_page=fitz_page,
                extraction_method=page.extraction_method or "native",
                ocr_layout_json=page.ocr_layout_json,
            )
            lines_by_page[page.page_number] = lines
            if lines:
                pages_with_geometry += 1
            context_input.append((page.page_number, lines, page.page_height or 0.0))
    finally:
        if fitz_doc is not None:
            fitz_doc.close()

    doc_context = build_document_context(pages=context_input)

    regions_by_page = {
        page.page_number: classify_page_regions(
            page_number=page.page_number,
            blocks=lines_by_page[page.page_number],
            tables=page.tables_json,
            page_height=page.page_height or 0.0,
            doc_context=doc_context,
        )
        for page in pages
    }

    citations = scan_pages_for_clause_citations(pages=pages, regions_by_page=regions_by_page)

    clin_rows: list[ParsedClinRow] = []
    for page in pages:
        clin_rows.extend(parse_clin_rows(page=page))

    candidates: list[ClassifiedCandidate] = []
    for page in pages:
        form_cells = associate_form_cells(lines=lines_by_page[page.page_number])
        candidates.extend(route_form_cell_associations(form_cells))
        # Structural regions only — FORM_FIELD_LABEL/VALUE already routed
        # above via line-level form-cell ownership; routing them again here
        # would double-pair the same lines.
        structural_only = [
            region
            for region in regions_by_page[page.page_number]
            if region.region_type not in ("FORM_FIELD_LABEL", "FORM_FIELD_VALUE")
        ]
        candidates.extend(route_page_regions(structural_only))

    candidates.extend(route_clause_citations(citations))
    candidates.extend(route_clin_rows(clin_rows))
    candidates = deduplicate_clin_funding_overlap(candidates)

    if pages_with_geometry == 0:
        warnings.append(
            "V3 classification: no page had usable line geometry (neither "
            "native text nor a captured OCR layer) — form-field pairing "
            "and heading/TOC detection were skipped for every page; only "
            "clause-citation and CLIN-line regex extraction ran."
        )

    return V3ClassificationResult(
        candidates=candidates,
        clause_citations=citations,
        clin_rows=clin_rows,
        pages_classified=len(pages),
        pages_with_geometry=pages_with_geometry,
        warnings=warnings,
    )
