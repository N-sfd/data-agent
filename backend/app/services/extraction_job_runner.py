from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.extraction_job import ExtractionJob
from app.services.ai_provider_factory import create_ai_provider
from app.services.detected_target_store import persist_document_targets
from app.services.document_extraction import (
    DocumentExtractionError,
    process_document_pages,
)
from app.services.document_storage import (
    DocumentStorageError,
    ensure_local_copy,
)
from app.services.schema_discovery import discover_document_schema
from app.services.target_extraction_service import extract_by_targets

settings = get_settings()

# extract_by_targets resolves each batch's fields against one shared
# document context; kept well under the request-schema's former cap so a
# single job can accept an unbounded target_id list from the frontend.
EXTRACTION_BATCH_SIZE = 50


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _fail_job(job: ExtractionJob, database, exc: Exception) -> None:
    job.status = "failed"
    job.error_message = str(exc)
    job.completed_at = datetime.now(timezone.utc)
    database.commit()


async def run_processing_job(job_id: int) -> None:
    """Background runner for a "processing" job: restore the file,
    extract native text/OCR/tables/pages, then discover the schema."""

    database = SessionLocal()

    try:
        job = database.get(ExtractionJob, job_id)
        if job is None:
            return

        document = database.get(Document, job.document_id)
        if document is None:
            _fail_job(job, database, ValueError("Document not found."))
            return

        job.status = "processing"
        job.stage = "processing_document"
        job.started_at = datetime.now(timezone.utc)
        job.progress = 5
        database.commit()

        try:
            file_path = await run_in_threadpool(
                ensure_local_copy,
                settings,
                stored_filename=document.stored_filename,
            )
        except DocumentStorageError as exc:
            _fail_job(job, database, exc)
            return

        try:
            result = await run_in_threadpool(
                process_document_pages,
                database=database,
                document_record=document,
                file_path=file_path,
                settings=settings,
                run_ocr=True,
                page_start=None,
                page_end=None,
                force_reprocess=False,
            )
        except DocumentExtractionError as exc:
            _fail_job(job, database, exc)
            return

        if result.get("ocr_required_page_count", 0) > 0:
            job.stage = "running_ocr"
        job.progress = 60
        database.commit()

        job.stage = "discovering_fields"
        database.commit()

        pages = list(
            database.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document.id)
                .order_by(DocumentPage.page_number)
            )
        )

        ai_provider = create_ai_provider(settings)

        try:
            schema_result = await discover_document_schema(
                document=document,
                pages=pages,
                ai_provider=ai_provider,
            )
            persist_document_targets(database=database, result=schema_result)
        except Exception as exc:  # noqa: BLE001 - surfaced via job status
            _fail_job(job, database, exc)
            return

        job.status = "complete"
        job.stage = "complete"
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        database.commit()

    finally:
        database.close()


async def run_extraction_job(
    job_id: int,
    target_ids: list[str],
    use_ai_fallback: bool,
) -> None:
    """Background runner for an "extraction" job: extract the selected
    targets, batching internally so the caller never sees a batch limit."""

    database = SessionLocal()

    try:
        job = database.get(ExtractionJob, job_id)
        if job is None:
            return

        document = database.get(Document, job.document_id)
        if document is None:
            _fail_job(job, database, ValueError("Document not found."))
            return

        job.status = "processing"
        job.stage = "extracting_data"
        job.started_at = datetime.now(timezone.utc)
        database.commit()

        ai_provider = create_ai_provider(settings)

        batches = _chunk(target_ids, EXTRACTION_BATCH_SIZE)
        scalars: list[dict] = []
        tables: list[dict] = []
        unresolved: list[str] = []
        warnings: list[str] = []

        for index, batch in enumerate(batches):
            try:
                batch_result = await extract_by_targets(
                    database=database,
                    document=document,
                    target_ids=batch,
                    use_ai_fallback=use_ai_fallback,
                    ai_provider=ai_provider,
                )
            except Exception as exc:  # noqa: BLE001 - surfaced via job status
                _fail_job(job, database, exc)
                return

            scalars.extend(
                scalar.model_dump(mode="json")
                for scalar in batch_result.scalars
            )
            tables.extend(
                table.model_dump(mode="json") for table in batch_result.tables
            )
            unresolved.extend(batch_result.unresolved_targets)
            warnings.extend(batch_result.warnings)

            job.progress = round((index + 1) / len(batches) * 80)
            database.commit()

        job.stage = "validating_results"
        database.commit()

        job.result_json = {
            "document_id": document.id,
            "scalars": scalars,
            "tables": tables,
            "unresolved_targets": unresolved,
            "warnings": warnings,
        }
        job.status = "complete"
        job.stage = "complete"
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        database.commit()

    finally:
        database.close()
