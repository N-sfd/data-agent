from datetime import datetime, timedelta, timezone

from app.models.extraction_job import ExtractionJob

INTERRUPTED_MESSAGE = "Interrupted by a server restart."

# Jobs run in-process, so a job is only orphaned once its process is gone.
# During a rolling deploy the old instance keeps running its jobs while the
# new one boots, so "queued/processing at startup" does not mean orphaned.
# Only a job older than any plausible run is treated as dead.
STALE_JOB_AFTER = timedelta(minutes=30)

ACTIVE_STATUSES = ("queued", "processing")


def _as_utc(value: datetime) -> datetime:
    # SQLite hands back naive datetimes; everything is stored in UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def is_orphaned(job: ExtractionJob, now: datetime | None = None) -> bool:
    if job.status not in ACTIVE_STATUSES:
        return False
    began = job.started_at or job.created_at
    if began is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now - _as_utc(began) > STALE_JOB_AFTER


def mark_interrupted(job: ExtractionJob, now: datetime | None = None) -> None:
    job.status = "failed"
    job.error_message = INTERRUPTED_MESSAGE
    job.completed_at = now or datetime.now(timezone.utc)
