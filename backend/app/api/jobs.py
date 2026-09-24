from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.dependencies import get_database
from app.models.document import Document
from app.models.extraction_job import ExtractionJob
from app.schemas.extraction_job import (
    ExtractionJobResponse,
    StartExtractionJobRequest,
)
from app.services.extraction_job_runner import (
    run_extraction_job,
    run_in_worker_thread,
    run_processing_job,
)

# Document-scoped job creation, mounted at /api/documents alongside the
# existing synchronous endpoints (which remain unchanged).
router = APIRouter()

# The plain /v1/jobs/{job_id} status endpoint the spec calls for.
v1_router = APIRouter()


def _to_response(job: ExtractionJob) -> ExtractionJobResponse:
    return ExtractionJobResponse(
        id=job.id,
        document_id=job.document_id,
        job_type=job.job_type,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        error_message=job.error_message,
        retry_count=job.retry_count,
        result=job.result_json,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post(
    "/{document_id}/jobs/process",
    response_model=ExtractionJobResponse,
    status_code=202,
)
async def start_processing_job(
    document_id: str,
    background_tasks: BackgroundTasks,
    database: Session = Depends(get_database),
) -> ExtractionJobResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    job = ExtractionJob(document_id=document_id, job_type="processing")
    database.add(job)
    database.commit()
    database.refresh(job)

    background_tasks.add_task(run_in_worker_thread, run_processing_job, job.id)

    return _to_response(job)


@router.post(
    "/{document_id}/jobs/extract",
    response_model=ExtractionJobResponse,
    status_code=202,
)
async def start_extraction_job(
    document_id: str,
    request: StartExtractionJobRequest,
    background_tasks: BackgroundTasks,
    database: Session = Depends(get_database),
) -> ExtractionJobResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    job = ExtractionJob(document_id=document_id, job_type="extraction")
    database.add(job)
    database.commit()
    database.refresh(job)

    background_tasks.add_task(
        run_in_worker_thread,
        run_extraction_job,
        job.id,
        request.target_ids,
        request.use_ai_fallback,
    )

    return _to_response(job)


@v1_router.get(
    "/{job_id}",
    response_model=ExtractionJobResponse,
)
async def get_job(
    job_id: int,
    database: Session = Depends(get_database),
) -> ExtractionJobResponse:
    job = database.get(ExtractionJob, job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    return _to_response(job)
