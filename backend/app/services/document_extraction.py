import time
from datetime import datetime, timezone
from pathlib import Path

import fitz
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.page_text_block import PageTextBlock
from app.services.document_provider import (
    ConveraError,
    extract_document,
    should_use_convera_documents,
)
from app.services.generic_table_extractor import (
    extract_page_tables,
)
from app.services.page_text_extractor import extract_page
from app.services.pdf_form_extractor import (
    extract_page_form_fields,
)


class DocumentExtractionError(Exception):
    pass


def _summarize_stored_pages(
    *,
    database: Session,
    document_record: Document,
    started_at: float,
) -> dict:
    pages = list(
        database.scalars(
            select(DocumentPage).where(
                DocumentPage.document_id == document_record.id
            )
        )
    )

    document_record.processing_status = "completed"
    document_record.processed_page_count = len(pages)
    document_record.processing_duration_seconds = (
        time.monotonic() - started_at
    )
    database.commit()

    return {
        "document_id": document_record.id,
        "status": document_record.processing_status,
        "total_document_pages": document_record.page_count,
        "pages_requested": len(pages),
        "pages_processed": len(pages),
        "native_pages": len(pages),
        "ocr_required_pages": 0,
        "ocr_completed_pages": 0,
        "failed_pages": 0,
        "page_numbers_processed": [
            page.page_number for page in pages
        ],
        "warnings": [],
        "completed_at": datetime.now(timezone.utc),
    }


def resolve_page_range(
    *,
    total_pages: int,
    page_start: int | None,
    page_end: int | None,
) -> tuple[int, int]:
    first_page = page_start or 1
    last_page = page_end or total_pages

    if first_page > last_page:
        raise DocumentExtractionError(
            "page_start cannot be greater than page_end."
        )

    if first_page < 1:
        raise DocumentExtractionError(
            "page_start must be at least 1."
        )

    if last_page > total_pages:
        raise DocumentExtractionError(
            f"The PDF contains only {total_pages} pages."
        )

    return first_page, last_page


def _process_pdf_via_convera(
    *,
    database: Session,
    document_record: Document,
    file_path: Path,
    settings: Settings,
    started_at: float,
) -> dict:
    try:
        normalized = extract_document(
            file_path,
            settings=settings,
        )
    except ConveraError as exc:
        raise DocumentExtractionError(str(exc)) from exc

    pages = normalized.get("pages", [])
    ocr_required = normalized.get("ocr_required", False)

    database.execute(
        delete(DocumentPage).where(
            DocumentPage.document_id == document_record.id
        )
    )
    database.flush()

    for page in pages:
        page_number = page.get("page", 1)
        text = page.get("text", "")

        # Convera's extraction payload doesn't always include page
        # dimensions; page_width/page_height are NOT NULL columns with
        # no default, so fall back to standard US Letter (in PDF
        # points) rather than failing the insert.
        page_width = page.get("width") or page.get("page_width") or 612.0
        page_height = (
            page.get("height") or page.get("page_height") or 792.0
        )

        # Convera's current API doesn't return table data (confirmed
        # against the live service), and Data Agent's table detection
        # has always been local/deterministic (pdfplumber) rather than
        # sourced from a document-AI response — run it against the
        # original file the same way the local extraction path does,
        # so downstream code (normalize_document_tables) sees the same
        # DocumentPage.tables_json shape regardless of which pipeline
        # produced the page text. Tolerate pdfplumber failures (e.g. a
        # scanned, image-only page) rather than failing the upload.
        try:
            page_tables = extract_page_tables(file_path, page_number)
        except Exception:
            page_tables = []

        database.add(
            DocumentPage(
                document_id=document_record.id,
                page_number=page_number,
                page_label=str(page_number),
                native_text=text,
                ocr_text=None,
                final_text=text,
                tables_json=page_tables or None,
                has_tables=bool(page_tables),
                is_scanned=ocr_required,
                text_length=len(text),
                extraction_method="convera",
                requires_ocr=ocr_required,
                ocr_attempted=False,
                ocr_succeeded=False,
                character_count=len(text),
                word_count=len(text.split()),
                page_width=page_width,
                page_height=page_height,
                extraction_status="completed",
                extracted_at=datetime.now(timezone.utc),
            )
        )

    database.commit()

    return _summarize_stored_pages(
        database=database,
        document_record=document_record,
        started_at=started_at,
    )


def process_document_pages(
    *,
    database: Session,
    document_record: Document,
    file_path: Path,
    settings: Settings,
    run_ocr: bool,
    page_start: int | None,
    page_end: int | None,
    force_reprocess: bool,
) -> dict:
    started_at = time.monotonic()

    if not file_path.exists():
        raise DocumentExtractionError(
            "The stored document file could not be found."
        )

    if file_path.suffix.lower() == ".docx":
        # DOCX text is extracted synchronously at upload time (it's
        # already digital, no OCR/page-image pipeline applies) — just
        # report back what's already stored.
        return _summarize_stored_pages(
            database=database,
            document_record=document_record,
            started_at=started_at,
        )

    if (
        should_use_convera_documents(settings)
        and file_path.suffix.lower() == ".pdf"
    ):
        return _process_pdf_via_convera(
            database=database,
            document_record=document_record,
            file_path=file_path,
            settings=settings,
            started_at=started_at,
        )

    # Raster images open as a 1-page fitz document (so the text/OCR path
    # below works unchanged), but they have no real PDF structure, so
    # the PDF-specific form-field and table extractors can't run on them.
    is_raster_image = file_path.suffix.lower() in {
        ".png",
        ".jpg",
        ".jpeg",
    }

    pdf: fitz.Document | None = None

    try:
        pdf = fitz.open(file_path)

        first_page, last_page = resolve_page_range(
            total_pages=pdf.page_count,
            page_start=page_start,
            page_end=page_end,
        )

        requested_page_numbers = list(
            range(first_page, last_page + 1)
        )

        document_record.processing_status = "processing"
        database.commit()

        native_pages = 0
        ocr_required_pages = 0
        ocr_completed_pages = 0
        failed_pages = 0
        processed_pages: list[int] = []
        warnings: list[str] = []

        for page_number in requested_page_numbers:
            existing_page = database.scalar(
                select(DocumentPage).where(
                    DocumentPage.document_id
                    == document_record.id,
                    DocumentPage.page_number
                    == page_number,
                )
            )

            if existing_page and not force_reprocess:
                processed_pages.append(page_number)

                if existing_page.requires_ocr:
                    ocr_required_pages += 1

                if existing_page.ocr_succeeded:
                    ocr_completed_pages += 1

                if existing_page.extraction_method == "native":
                    native_pages += 1

                continue

            if existing_page and force_reprocess:
                database.execute(
                    delete(PageTextBlock).where(
                        PageTextBlock.document_page_id
                        == existing_page.id
                    )
                )

                database.delete(existing_page)
                database.flush()

            try:
                extracted = extract_page(
                    document=pdf,
                    page_index=page_number - 1,
                    settings=settings,
                    run_ocr=run_ocr,
                )

                if is_raster_image:
                    form_fields: dict[str, str] = {}
                    page_tables: list[dict] = []
                else:
                    fitz_page = pdf.load_page(page_number - 1)

                    form_fields = extract_page_form_fields(
                        fitz_page
                    )

                    page_tables = extract_page_tables(
                        file_path,
                        page_number,
                    )

                page_record = DocumentPage(
                    document_id=document_record.id,
                    page_number=extracted.page_number,
                    page_label=extracted.page_label,
                    native_text=extracted.native_text,
                    ocr_text=extracted.ocr_text,
                    final_text=extracted.final_text,
                    form_fields_json=(
                        form_fields or None
                    ),
                    tables_json=page_tables or None,
                    has_tables=bool(page_tables),
                    has_form_fields=bool(form_fields),
                    is_scanned=(
                        extracted.extraction_method == "ocr"
                        or extracted.detection.requires_ocr
                    ),
                    text_length=len(extracted.final_text),
                    extraction_method=extracted.extraction_method,
                    requires_ocr=(
                        extracted.detection.requires_ocr
                    ),
                    ocr_attempted=extracted.ocr_attempted,
                    ocr_succeeded=extracted.ocr_succeeded,
                    ocr_language=(
                        settings.ocr_language
                        if extracted.ocr_attempted
                        else None
                    ),
                    ocr_error=extracted.ocr_error,
                    character_count=len(extracted.final_text),
                    word_count=len(
                        extracted.final_text.split()
                    ),
                    text_block_count=(
                        extracted.detection.text_block_count
                    ),
                    image_count=(
                        extracted.detection.image_count
                    ),
                    text_coverage_ratio=(
                        extracted.detection
                        .text_coverage_ratio
                    ),
                    image_coverage_ratio=(
                        extracted.detection
                        .image_coverage_ratio
                    ),
                    page_width=extracted.page_width,
                    page_height=extracted.page_height,
                    extraction_status=(
                        "completed"
                        if not extracted.ocr_error
                        else "completed_with_warning"
                    ),
                    extracted_at=datetime.now(timezone.utc),
                )

                database.add(page_record)
                database.flush()

                for block in extracted.blocks:
                    database.add(
                        PageTextBlock(
                            document_page_id=page_record.id,
                            block_index=block.block_index,
                            block_type=block.block_type,
                            text=block.text,
                            x0=block.x0,
                            y0=block.y0,
                            x1=block.x1,
                            y1=block.y1,
                            extraction_method=(
                                block.extraction_method
                            ),
                        )
                    )

                processed_pages.append(page_number)

                if extracted.detection.requires_ocr:
                    ocr_required_pages += 1
                else:
                    native_pages += 1

                if extracted.ocr_succeeded:
                    ocr_completed_pages += 1

                if extracted.ocr_error:
                    warnings.append(
                        f"Page {page_number}: OCR failed: "
                        f"{extracted.ocr_error}"
                    )

                database.commit()

            except Exception as exc:
                database.rollback()
                failed_pages += 1

                warnings.append(
                    f"Page {page_number}: extraction failed: {exc}"
                )

        total_processed_statement = select(
            DocumentPage
        ).where(
            DocumentPage.document_id == document_record.id
        )

        all_stored_pages = list(
            database.scalars(total_processed_statement)
        )

        document_record.processed_page_count = len(
            all_stored_pages
        )

        document_record.ocr_required_page_count = sum(
            1
            for page in all_stored_pages
            if page.requires_ocr
        )

        document_record.ocr_completed_page_count = sum(
            1
            for page in all_stored_pages
            if page.ocr_succeeded
        )

        if failed_pages > 0 or warnings:
            document_record.processing_status = (
                "completed_with_warnings"
            )
        else:
            document_record.processing_status = "completed"

        document_record.processing_duration_seconds = (
            time.monotonic() - started_at
        )

        database.commit()

        return {
            "document_id": document_record.id,
            "status": document_record.processing_status,
            "total_document_pages": pdf.page_count,
            "pages_requested": len(requested_page_numbers),
            "pages_processed": len(processed_pages),
            "native_pages": native_pages,
            "ocr_required_pages": ocr_required_pages,
            "ocr_completed_pages": ocr_completed_pages,
            "failed_pages": failed_pages,
            "page_numbers_processed": processed_pages,
            "warnings": warnings,
            "completed_at": datetime.now(timezone.utc),
        }

    except DocumentExtractionError:
        raise

    except Exception as exc:
        document_record.processing_status = "failed"
        database.commit()

        raise DocumentExtractionError(
            "The PDF could not be processed."
        ) from exc

    finally:
        if pdf is not None:
            pdf.close()
