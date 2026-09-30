from datetime import datetime, timedelta, timezone

from app.models.extraction_job import ExtractionJob
from app.services.job_recovery import (
    INTERRUPTED_MESSAGE,
    STALE_JOB_AFTER,
    is_orphaned,
    mark_interrupted,
)

NOW = datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)


def _job(status: str, age: timedelta, started: bool = True) -> ExtractionJob:
    began = NOW - age
    return ExtractionJob(
        document_id="doc-1",
        job_type="extraction",
        status=status,
        created_at=began,
        started_at=began if started else None,
    )


def test_recent_running_job_is_not_orphaned():
    # Another instance may still be running it during a rolling deploy.
    assert not is_orphaned(_job("processing", timedelta(minutes=2)), NOW)


def test_stale_running_job_is_orphaned():
    job = _job("processing", STALE_JOB_AFTER + timedelta(seconds=1))
    assert is_orphaned(job, NOW)


def test_stale_queued_job_uses_created_at():
    job = _job("queued", STALE_JOB_AFTER + timedelta(minutes=1), started=False)
    assert is_orphaned(job, NOW)


def test_finished_jobs_are_never_orphaned():
    for status in ("complete", "failed"):
        assert not is_orphaned(_job(status, timedelta(days=1)), NOW)


def test_naive_timestamps_are_treated_as_utc():
    job = _job("processing", STALE_JOB_AFTER + timedelta(minutes=1))
    job.started_at = job.started_at.replace(tzinfo=None)
    assert is_orphaned(job, NOW)


def test_mark_interrupted():
    job = _job("processing", timedelta(hours=1))
    mark_interrupted(job, NOW)
    assert job.status == "failed"
    assert job.error_message == INTERRUPTED_MESSAGE
    assert job.completed_at == NOW
