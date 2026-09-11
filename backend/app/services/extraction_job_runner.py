from datetime import datetime, timezone
import time

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.core.config import get_settings
from app.core.observability import bind_job_context, log_event
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.extraction_job import ExtractionJob
from app.services.ai_provider_factory import create_ai_provider, describe_ai_provider
from app.services.detected_target_store import persist_document_targets
from app.services.document_extraction import (
    DocumentExtractionError,
    process_document_pages,
)
from app.services.document_storage import (
    DocumentStorageError,
    ensure_local_copy,
)
from app.services.ingestion_provenance import merge_provenance
from app.services.schema_discovery import discover_document_schema
from app.services.target_extraction_service import extract_by_targets
from app.services.target_result_store import persist_target_extraction_results
from app.schemas.document_target import ScalarTargetResult, TableTargetResult

settings = get_settings()

# extract_by_targets resolves each batch's fields against one shared
# document context; kept well under the request-schema's former cap so a
# single job can accept an unbounded target_id list from the frontend.
EXTRACTION_BATCH_SIZE = 50

EMPTY_STRUCTURES_WARNING = (
    "Processing completed, but no extractable structures were detected."
)


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _append_stage(job: ExtractionJob, stage: str) -> None:
    payload = dict(job.result_json or {})
    history = list(payload.get("stage_history") or [])
    history.append(
        {
            "stage": stage,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    payload["stage_history"] = history
    if payload.get("warnings") is None:
        payload["warnings"] = []
    job.result_json = payload
    job.stage = stage


def _fail_job(job: ExtractionJob, database, exc: Exception) -> None:
    job.status = "failed"
    job.error_message = str(exc)
    job.completed_at = datetime.now(timezone.utc)
    database.commit()
    log_event(
        "job_failed",
        stage=job.stage or "unknown",
        status="error",
        error_category=type(exc).__name__,
        job_id=job.id,
        document_id=job.document_id,
    )


async def run_processing_job(job_id: int) -> None:
    """Background runner for a "processing" job: restore the file,
    extract native text/OCR/tables/pages, then discover the schema."""

    database = SessionLocal()
    started = time.perf_counter()

    try:
        job = database.get(ExtractionJob, job_id)
        if job is None:
            return

        document = database.get(Document, job.document_id)
        if document is None:
            _fail_job(job, database, ValueError("Document not found."))
            return

        bind_job_context(document_id=document.id, job_id=job.id)
        log_event(
            "job_started",
            stage="reading_document",
            job_type="processing",
        )

        job.status = "processing"
        _append_stage(job, "reading_document")
        job.started_at = datetime.now(timezone.utc)
        job.progress = 5
        merge_provenance(
            document,
            {
                "processing_mode": "background",
                "processing_job_id": job.id,
                "size_tier": (document.ingestion_provenance or {}).get(
                    "size_tier"
                ),
            },
        )
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

        _append_stage(job, "rendering_ocr")
        job.progress = 20
        database.commit()

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

        # Refresh after threadpool mutation.
        database.refresh(document)

        _append_stage(job, "indexing")
        job.progress = 60
        database.commit()

        _append_stage(job, "discovering_fields")
        job.progress = 75
        database.commit()

        pages = list(
            database.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document.id)
                .order_by(DocumentPage.page_number)
            )
        )

        page_text_chars = sum(len(page.final_text or "") for page in pages)

        ai_provider = create_ai_provider(settings)
        log_event(
            "schema_discovery_start",
            stage="discovering_fields",
            provider=describe_ai_provider(ai_provider),
            page_count=len(pages),
            page_text_chars=page_text_chars,
        )

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

        target_count = len(schema_result.targets)
        empty_warning = None
        if page_text_chars == 0 or target_count == 0:
            empty_warning = EMPTY_STRUCTURES_WARNING

        merge_provenance(
            document,
            {
                "page_text_chars": page_text_chars,
                "targets_discovered": target_count,
                "empty_extraction_warning": empty_warning,
                "processing_mode": "background",
                "processing_job_id": job.id,
            },
        )

        payload = dict(job.result_json or {})
        warnings = list(payload.get("warnings") or [])
        if empty_warning:
            warnings.append(empty_warning)
            log_event(
                "empty_extraction_warning",
                stage="complete",
                status="warning",
                page_text_chars=page_text_chars,
                target_count=target_count,
            )
        payload["warnings"] = warnings
        payload["page_text_chars"] = page_text_chars
        payload["targets_discovered"] = target_count
        job.result_json = payload

        job.status = "complete"
        _append_stage(job, "complete")
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        database.commit()
        log_event(
            "job_complete",
            stage="complete",
            job_type="processing",
            duration_ms=int((time.perf_counter() - started) * 1000),
            target_count=target_count,
            page_text_chars=page_text_chars,
            pages_processed=result.get("pages_processed"),
        )

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
    started = time.perf_counter()

    try:
        job = database.get(ExtractionJob, job_id)
        if job is None:
            return

        document = database.get(Document, job.document_id)
        if document is None:
            _fail_job(job, database, ValueError("Document not found."))
            return

        bind_job_context(document_id=document.id, job_id=job.id)

        job.status = "processing"
        _append_stage(job, "extracting_data")
        job.started_at = datetime.now(timezone.utc)
        database.commit()

        ai_provider = create_ai_provider(settings)
        log_event(
            "job_started",
            stage="extracting_data",
            job_type="extraction",
            provider=describe_ai_provider(ai_provider),
            target_count=len(target_ids),
            use_ai_fallback=use_ai_fallback,
        )

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

        _append_stage(job, "validating_results")
        database.commit()

        history = list((job.result_json or {}).get("stage_history") or [])
        job.result_json = {
            "document_id": document.id,
            "scalars": scalars,
            "tables": tables,
            "unresolved_targets": unresolved,
            "warnings": warnings,
            "stage_history": history,
        }

        persist_target_extraction_results(
            database=database,
            document_id=document.id,
            scalars=[
                ScalarTargetResult.model_validate(item) for item in scalars
            ],
            tables=[TableTargetResult.model_validate(item) for item in tables],
            extraction_job_id=job.id,
        )

        job.status = "complete"
        _append_stage(job, "complete")
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        database.commit()
        log_event(
            "job_complete",
            stage="complete",
            job_type="extraction",
            duration_ms=int((time.perf_counter() - started) * 1000),
            scalar_count=len(scalars),
            table_count=len(tables),
            unresolved_count=len(unresolved),
        )

    finally:
        database.close()
