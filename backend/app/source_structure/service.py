"""Builds, persists and loads a document's StructuredSourceDocument.

Per page, the best available geometry is used:
    native PDF text  → PyMuPDF words/spans (PDF points)
    scanned/OCR page → the persisted OCR word layer, transformed to PDF
                       points (ocr_geometry) — no new OCR pass
    HTML             → the DOM of the stored file
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_source_structure import DocumentSourceStructure
from app.services.document_storage import DocumentStorageError, ensure_local_copy
from app.source_structure.html_structure import extract_html_structure
from app.source_structure.models import StructuredSourceDocument
from app.source_structure.ocr_geometry import coordinate_space_for
from app.source_structure.table_continuity import annotate_geometry, link_continuations
from app.source_structure.pdf_structure import (
    extract_page_structure,
    native_words,
    ocr_words,
)

# Bump whenever extraction rules change; stored structures from an older
# version are rebuilt on next use.
EXTRACTOR_VERSION = 2  # 2: table continuation metadata, candidate quality flags

_HTML_SUFFIXES = {".html", ".htm"}
_RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
# Row/cell regions duplicate what TableCandidate cells already carry; they
# are not persisted to keep the stored artifact compact.
_TRANSIENT_REGION_TYPES = {"TABLE_ROW", "TABLE_CELL"}
_MAX_REJECTED_TABLE_ROWS = 5


def _source_type(document: Document) -> str:
    suffix = Path(document.stored_filename or "").suffix.lower()
    if suffix in _HTML_SUFFIXES:
        return "html"
    if suffix in _RASTER_SUFFIXES:
        return "image"
    return "pdf"


def _build_pdf(document: Document, pages: list[DocumentPage], file_path: Path | None, result: StructuredSourceDocument) -> None:
    import fitz

    settings = get_settings()
    fitz_doc = None
    if file_path is not None:
        try:
            if result.source_type == "image":
                from app.services.file_processors.image_processor import _ensure_fitz_readable

                file_path = _ensure_fitz_readable(file_path)
            fitz_doc = fitz.open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Could not open source file for geometry ({exc}).")

    try:
        for page in pages:
            fitz_page = None
            if fitz_doc is not None and 0 <= page.page_number - 1 < fitz_doc.page_count:
                fitz_page = fitz_doc[page.page_number - 1]
            words, method = [], "native"
            if fitz_page is not None:
                words = native_words(fitz_page)
            if len(words) < 3 and page.ocr_layout_json:
                space = coordinate_space_for(
                    page.ocr_layout_json,
                    page_width_pt=page.page_width or (fitz_page.rect.width if fitz_page else 612.0),
                    page_height_pt=page.page_height or (fitz_page.rect.height if fitz_page else 792.0),
                    ocr_dpi=settings.ocr_dpi,
                )
                if space is not None:
                    words, method = ocr_words(page.ocr_layout_json, space), "ocr"
            if not words:
                continue
            structure = extract_page_structure(
                page_number=page.page_number,
                words=words,
                extraction_method=method,
                fitz_page=fitz_page,
            )
            page_height = page.page_height or (fitz_page.rect.height if fitz_page else None)
            for table in structure.tables:
                annotate_geometry(table, page_height)
            result.regions.extend(structure.regions)
            result.field_candidates.extend(structure.fields)
            result.table_candidates.extend(structure.tables)
        link_continuations(result.table_candidates)
    finally:
        if fitz_doc is not None:
            fitz_doc.close()


def _build_html(file_path: Path | None, result: StructuredSourceDocument) -> None:
    if file_path is None:
        result.warnings.append("HTML source file unavailable; no structure extracted.")
        return
    extractor = extract_html_structure(file_path.read_bytes())
    result.regions.extend(extractor.regions)
    result.field_candidates.extend(extractor.fields)
    for table in extractor.tables:
        annotate_geometry(table, None)
    result.table_candidates.extend(extractor.tables)


def build_source_structure(database: Session, document: Document) -> StructuredSourceDocument:
    started = time.perf_counter()
    pages = list(
        database.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        )
    )
    result = StructuredSourceDocument(
        document_id=document.id,
        source_type=_source_type(document),
        extractor_version=EXTRACTOR_VERSION,
    )
    file_path: Path | None
    try:
        file_path = ensure_local_copy(get_settings(), stored_filename=document.stored_filename)
    except DocumentStorageError as exc:
        file_path = None
        result.warnings.append(f"Source file unavailable ({exc}).")

    if result.source_type == "html":
        _build_html(file_path, result)
    else:
        _build_pdf(document, pages, file_path, result)

    result.stats.pages = len(pages) if result.source_type != "html" else 0
    result.stats.regions_by_type = dict(Counter(r.region_type for r in result.regions))
    result.stats.field_candidates = dict(Counter(f.acceptance for f in result.field_candidates))
    result.stats.table_candidates = dict(Counter(t.acceptance for t in result.table_candidates))
    result.stats.duration_ms = int((time.perf_counter() - started) * 1000)
    return result


def _compact(structure: StructuredSourceDocument) -> dict:
    compact = structure.model_copy(deep=True)
    compact.regions = [r for r in compact.regions if r.region_type not in _TRANSIENT_REGION_TYPES]
    for table in compact.table_candidates:
        if table.acceptance != "accepted":
            table.rows = table.rows[:_MAX_REJECTED_TABLE_ROWS]
    return compact.model_dump(mode="json")


def build_and_persist_source_structure(
    database: Session, document: Document
) -> StructuredSourceDocument:
    structure = build_source_structure(database, document)
    record = database.scalars(
        select(DocumentSourceStructure).where(DocumentSourceStructure.document_id == document.id)
    ).first()
    if record is None:
        record = DocumentSourceStructure(document_id=document.id)
        database.add(record)
    record.extractor_version = EXTRACTOR_VERSION
    record.source_type = structure.source_type
    record.payload_json = _compact(structure)
    database.commit()
    return structure


def load_source_structure(database: Session, document_id: str) -> StructuredSourceDocument | None:
    record = database.scalars(
        select(DocumentSourceStructure).where(DocumentSourceStructure.document_id == document_id)
    ).first()
    if record is None or record.extractor_version != EXTRACTOR_VERSION:
        return None
    return StructuredSourceDocument.model_validate(record.payload_json)


def get_or_build_source_structure(
    database: Session, document: Document
) -> StructuredSourceDocument:
    """Stored structure when current; otherwise (older extraction, or an
    extractor upgrade) rebuilt and stored."""

    return load_source_structure(database, document.id) or build_and_persist_source_structure(
        database, document
    )
