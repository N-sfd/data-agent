import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import PAGE_EXTRACTION_FAILED
from app.models.document import Document
from app.services.document_extraction import DocumentExtractionError
from app.services.file_processors.base import FileProcessor
from app.services.file_processors.docx_processor import DocxProcessor
from app.services.file_processors.native_page_processor import (
    NativePageProcessor,
)
from app.services.libreoffice_convert import (
    LibreOfficeConversionError,
    convert_legacy_office,
)


class LegacyOfficeProcessor(FileProcessor):
    """DOC/XLS/PPT → LibreOffice OOXML → native processors."""

    kind = "legacy_office"

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
                "The stored Office document could not be found.",
                code=PAGE_EXTRACTION_FAILED,
            )

        try:
            converted = convert_legacy_office(file_path)
        except LibreOfficeConversionError as exc:
            raise DocumentExtractionError(
                str(exc),
                code=PAGE_EXTRACTION_FAILED,
            ) from exc

        out_dir = converted.parent
        try:
            suffix = converted.suffix.lower()
            if suffix == ".docx":
                processor: FileProcessor = DocxProcessor()
                # Ensure DOCX pages exist: DocxProcessor only summarizes.
                from app.services.native_ingest import ingest_native_document
                from app.services.security_validation import (
                    resolve_upload_type,
                )
                from sqlalchemy import delete, select
                from app.models.document_page import DocumentPage

                existing = list(
                    database.scalars(
                        select(DocumentPage).where(
                            DocumentPage.document_id
                            == document_record.id
                        )
                    )
                )
                if force_reprocess or not existing:
                    if existing:
                        database.execute(
                            delete(DocumentPage).where(
                                DocumentPage.document_id
                                == document_record.id
                            )
                        )
                        database.flush()
                    page_count = ingest_native_document(
                        database,
                        document_record.id,
                        converted,
                        resolve_upload_type(".docx"),
                    )
                    document_record.page_count = page_count
                    database.commit()

                return processor.process(
                    database=database,
                    document_record=document_record,
                    file_path=converted,
                    settings=settings,
                    run_ocr=run_ocr,
                    page_start=page_start,
                    page_end=page_end,
                    force_reprocess=False,
                    started_at=started_at,
                )

            return NativePageProcessor().process(
                database=database,
                document_record=document_record,
                file_path=converted,
                settings=settings,
                run_ocr=run_ocr,
                page_start=page_start,
                page_end=page_end,
                force_reprocess=force_reprocess,
                started_at=started_at,
            )
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)
