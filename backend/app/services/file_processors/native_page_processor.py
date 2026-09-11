from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import PAGE_EXTRACTION_FAILED
from app.models.document import Document
from app.services.document_extraction import (
    DocumentExtractionError,
    summarize_stored_pages,
)
from app.services.file_processors.base import FileProcessor
from app.services.native_ingest import ingest_native_document
from app.services.security_validation import resolve_upload_type


class NativePageProcessor(FileProcessor):
    """TXT/CSV/HTML/RTF/XLSX/PPTX — native text into DocumentPage rows."""

    kind = "native"

    def process(
        self,
        *,
        database: Session,
        document_record: Document,
        file_path: Path,
        settings: Settings,
        run_ocr: bool,
        page_start: int | None,
        page_end: int | None,
        force_reprocess: bool,
        started_at: float,
    ) -> dict:
        if not file_path.exists():
            raise DocumentExtractionError(
                "The stored document could not be found.",
                code=PAGE_EXTRACTION_FAILED,
            )

        from sqlalchemy import delete, select

        from app.models.document_page import DocumentPage

        existing = list(
            database.scalars(
                select(DocumentPage).where(
                    DocumentPage.document_id == document_record.id
                )
            )
        )

        if force_reprocess or not existing:
            if existing:
                database.execute(
                    delete(DocumentPage).where(
                        DocumentPage.document_id == document_record.id
                    )
                )
                database.flush()

            spec = resolve_upload_type(file_path.suffix.lower())
            page_count = ingest_native_document(
                database,
                document_record.id,
                file_path,
                spec,
            )
            document_record.page_count = page_count
            database.commit()

        return summarize_stored_pages(
            database=database,
            document_record=document_record,
            started_at=started_at,
        )
