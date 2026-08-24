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


class DocxProcessor(FileProcessor):
    kind = "docx"

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
                "The stored Word document could not be found.",
                code=PAGE_EXTRACTION_FAILED,
            )

        # Paragraphs, headings, tables, and lists are ingested at upload
        # time. /extract-pages reports the already-stored synthetic page.
        return summarize_stored_pages(
            database=database,
            document_record=document_record,
            started_at=started_at,
        )
