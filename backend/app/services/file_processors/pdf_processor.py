from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import PAGE_EXTRACTION_FAILED
from app.models.document import Document
from app.services.document_extraction import (
    DocumentExtractionError,
    process_fitz_pages,
    process_pdf_via_convera,
)
from app.services.document_provider import should_use_convera_documents
from app.services.file_processors.base import FileProcessor


class PdfProcessor(FileProcessor):
    kind = "pdf"

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
                "The stored PDF could not be found.",
                code=PAGE_EXTRACTION_FAILED,
            )

        if should_use_convera_documents(settings):
            return process_pdf_via_convera(
                database=database,
                document_record=document_record,
                file_path=file_path,
                settings=settings,
                started_at=started_at,
            )

        return process_fitz_pages(
            database=database,
            document_record=document_record,
            file_path=file_path,
            settings=settings,
            run_ocr=run_ocr,
            page_start=page_start,
            page_end=page_end,
            force_reprocess=force_reprocess,
            started_at=started_at,
            is_raster_image=False,
        )
