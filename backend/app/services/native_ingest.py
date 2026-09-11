"""Persist native-parser output as DocumentPage rows (common page model)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document_page import DocumentPage
from app.models.page_text_block import PageTextBlock
from app.parsers.docx_parser import parse_docx
from app.parsers.office_text_parsers import (
    parse_csv_file,
    parse_html_file,
    parse_plain_text,
    parse_pptx_slides,
    parse_rtf_file,
    parse_xlsx_sheets,
)
from app.services.security_validation import UploadTypeSpec


def _store_page(
    *,
    database: Session,
    document_id: str,
    page_number: int,
    page_label: str | None,
    paragraphs: list[str],
    tables: list,
    final_text: str,
    extraction_method: str = "native",
) -> None:
    page_record = DocumentPage(
        document_id=document_id,
        page_number=page_number,
        page_label=page_label,
        native_text=final_text,
        ocr_text=None,
        final_text=final_text,
        tables_json=tables or None,
        has_tables=bool(tables),
        has_form_fields=False,
        is_scanned=False,
        text_length=len(final_text),
        extraction_method=extraction_method,
        requires_ocr=False,
        ocr_attempted=False,
        ocr_succeeded=False,
        character_count=len(final_text),
        word_count=len(final_text.split()),
        text_block_count=len(paragraphs),
        image_count=0,
        text_coverage_ratio=1.0 if final_text.strip() else 0.0,
        image_coverage_ratio=0.0,
        page_width=0.0,
        page_height=0.0,
        extraction_status="completed",
        extracted_at=datetime.now(timezone.utc),
    )

    database.add(page_record)
    database.flush()

    for index, paragraph in enumerate(paragraphs):
        database.add(
            PageTextBlock(
                document_page_id=page_record.id,
                block_index=index,
                block_type="text",
                text=paragraph,
                x0=0.0,
                y0=0.0,
                x1=0.0,
                y1=0.0,
                extraction_method=extraction_method,
            )
        )


def ingest_native_document(
    database: Session,
    document_id: UUID | str,
    file_path: Path,
    spec: UploadTypeSpec,
) -> int:
    """Ingest native text/tables. Returns page count written."""

    doc_id = str(document_id)
    kind = spec.kind

    if kind == "docx":
        parsed = parse_docx(str(file_path))
        text_parts = list(parsed["paragraphs"])
        for table in parsed["tables"]:
            for row in table:
                text_parts.append(" | ".join(row))
        final_text = "\n".join(text_parts)
        _store_page(
            database=database,
            document_id=doc_id,
            page_number=1,
            page_label=None,
            paragraphs=parsed["paragraphs"],
            tables=parsed["tables"],
            final_text=final_text,
        )
        return 1

    if kind == "xlsx":
        sheets = parse_xlsx_sheets(file_path)
        if not sheets:
            sheets = [
                {
                    "name": "Sheet1",
                    "paragraphs": [],
                    "tables": [],
                    "text": "",
                }
            ]
        for index, sheet in enumerate(sheets, start=1):
            _store_page(
                database=database,
                document_id=doc_id,
                page_number=index,
                page_label=sheet["name"],
                paragraphs=sheet["paragraphs"],
                tables=sheet["tables"],
                final_text=sheet["text"],
            )
        return len(sheets)

    if kind == "pptx":
        slides = parse_pptx_slides(file_path)
        if not slides:
            slides = [
                {
                    "name": "Slide 1",
                    "paragraphs": [],
                    "tables": [],
                    "text": "",
                }
            ]
        for index, slide in enumerate(slides, start=1):
            _store_page(
                database=database,
                document_id=doc_id,
                page_number=index,
                page_label=slide["name"],
                paragraphs=slide["paragraphs"],
                tables=slide["tables"],
                final_text=slide["text"],
            )
        return len(slides)

    if kind == "csv":
        parsed = parse_csv_file(file_path)
    elif kind == "html":
        parsed = parse_html_file(file_path)
    elif kind == "rtf":
        parsed = parse_rtf_file(file_path)
    elif kind == "text":
        parsed = parse_plain_text(file_path)
    else:
        raise ValueError(f"No native ingest for kind={kind}")

    _store_page(
        database=database,
        document_id=doc_id,
        page_number=1,
        page_label=None,
        paragraphs=parsed["paragraphs"],
        tables=parsed["tables"],
        final_text=parsed["text"],
    )
    return 1
