"""Helpers for medium/large upload background processing."""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.extraction_job import ExtractionJob
from app.services.extraction_job_runner import run_processing_job
from app.services.ingestion_provenance import (
    empty_provenance,
    merge_provenance,
    processor_label_for_extension,
)
from app.services.libreoffice_convert import (
    LEGACY_OFFICE_UNAVAILABLE,
    libreoffice_available,
)
from app.services.security_validation import UploadTypeSpec
from app.services.upload_size_tiers import (
    classify_upload_size,
    prefer_background_processing,
)


def assert_legacy_office_supported(spec: UploadTypeSpec) -> None:
    if spec.kind == "legacy_office" and not libreoffice_available():
        from app.services.file_upload import UploadValidationError

        raise UploadValidationError(LEGACY_OFFICE_UNAVAILABLE)


def seed_upload_provenance(
    document: Document,
    *,
    spec: UploadTypeSpec,
    size_bytes: int,
) -> dict:
    tier = classify_upload_size(size_bytes)
    provenance = empty_provenance(
        source_format=spec.extension,
        size_tier=tier,
    )
    provenance["processor"] = processor_label_for_extension(spec.extension)
    document.ingestion_provenance = provenance
    return provenance


def enqueue_processing_job(
    *,
    database: Session,
    background_tasks: BackgroundTasks,
    document_id: str,
) -> int:
    job = ExtractionJob(document_id=document_id, job_type="processing")
    database.add(job)
    database.commit()
    database.refresh(job)
    background_tasks.add_task(run_processing_job, job.id)
    return job.id


def upload_processing_plan(size_bytes: int) -> tuple[str, bool]:
    tier = classify_upload_size(size_bytes)
    return tier, prefer_background_processing(size_bytes)


def finalize_processor_provenance(
    document: Document,
    *,
    extension: str,
    page_count: int,
    ocr_pages: list[int] | None = None,
    conversion_used: bool = False,
    converted_format: str | None = None,
) -> dict:
    ocr_pages = ocr_pages or []
    return merge_provenance(
        document,
        {
            "processor": processor_label_for_extension(
                extension, conversion_used=conversion_used
            ),
            "conversion_used": conversion_used,
            "converted_format": converted_format,
            "ocr_used": bool(ocr_pages),
            "ocr_pages": ocr_pages,
            "page_count": page_count,
        },
    )
