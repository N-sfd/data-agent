from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    contract_analysis,
    dashboard,
    documents,
    extraction_models,
    financial_analysis,
    jobs,
    page_extraction,
    system,
    universal_extraction,
)
from app.core.config import get_settings
from app.database.base import Base
from app.database.migrate import (
    ensure_document_metadata_field_columns,
    ensure_document_page_columns,
    ensure_documents_columns,
    ensure_extraction_model_columns,
    run_alembic_upgrade,
)
from app.database.session import engine
from app.services.document_storage import is_remote_storage_configured
from app.models import (  # noqa: F401
    classification_audit_log as classification_audit_log_model,
)
from app.models import document as document_model  # noqa: F401
from app.models import extraction_job as extraction_job_model  # noqa: F401
from app.models import document_address as document_address_model  # noqa: F401
from app.models import (  # noqa: F401
    document_amendment_history as document_amendment_history_model,
)
from app.models import document_clause as document_clause_model  # noqa: F401
from app.models import (  # noqa: F401
    document_clause_reference as document_clause_reference_model,
)
from app.models import document_contact as document_contact_model  # noqa: F401
from app.models import (  # noqa: F401
    document_delivery_schedule as document_delivery_schedule_model,
)
from app.models import (  # noqa: F401
    document_detected_target as document_detected_target_model,
)
from app.models import (  # noqa: F401
    document_funding_line as document_funding_line_model,
)
from app.models import (  # noqa: F401
    document_insurance_requirement as document_insurance_requirement_model,
)
from app.models import (  # noqa: F401
    document_key_position as document_key_position_model,
)
from app.models import document_line_item as document_line_item_model  # noqa: F401
from app.models import (  # noqa: F401
    document_metadata_field as document_metadata_field_model,
)
from app.models import document_order_range as document_order_range_model  # noqa: F401
from app.models import document_page as document_page_model  # noqa: F401
from app.models import (  # noqa: F401
    document_performance_period as document_performance_period_model,
)
from app.models import (  # noqa: F401
    document_signature as document_signature_model,
)
from app.models import (  # noqa: F401
    document_wawf_instruction as document_wawf_instruction_model,
)
from app.models import (  # noqa: F401
    extraction_model as extraction_model_model,
)
from app.models import (  # noqa: F401
    metadata_field_audit_log as metadata_field_audit_log_model,
)
from app.models import page_text_block as page_text_block_model  # noqa: F401
from app.models import (  # noqa: F401
    relationship_audit_log as relationship_audit_log_model,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Extract specific financial information and tables from PDFs "
        "and prepare Oracle Fusion dry-run payloads."
    ),
    version="0.1.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=(
        r"https?://("
        r"localhost|"
        r"127\.0\.0\.1|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?"
        if settings.debug
        else r"https://([a-z0-9-]+\.)*vercel\.app"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    documents.router,
    prefix="/api/documents",
    tags=["Documents"],
)

app.include_router(
    page_extraction.router,
    prefix="/api/documents",
    tags=["Page Extraction"],
)

app.include_router(
    financial_analysis.router,
    prefix="/api/documents",
    tags=["Financial Analysis"],
)

app.include_router(
    universal_extraction.router,
    prefix="/api/documents",
    tags=["Universal Extraction"],
)

app.include_router(
    contract_analysis.router,
    prefix="/api/documents",
    tags=["Contract Analysis"],
)

app.include_router(
    extraction_models.router,
    prefix="/api/extraction-models",
    tags=["Extraction Models"],
)

app.include_router(
    dashboard.router,
    prefix="/api/dashboard",
    tags=["Dashboard"],
)

app.include_router(
    system.router,
    prefix="/api/system",
    tags=["System"],
)

app.include_router(
    jobs.router,
    prefix="/api/documents",
    tags=["Jobs"],
)

app.include_router(
    jobs.v1_router,
    prefix="/v1/jobs",
    tags=["Jobs"],
)


@app.on_event("startup")
async def create_database_tables() -> None:
    if settings.app_env == "production":
        if settings.resolved_database_url.startswith("sqlite"):
            raise RuntimeError(
                "APP_ENV=production requires a persistent PostgreSQL "
                "DATABASE_URL — refusing to start on ephemeral SQLite, "
                "which does not survive a restart or redeploy."
            )

        if not is_remote_storage_configured(settings):
            raise RuntimeError(
                "APP_ENV=production requires SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY to be set — refusing to start "
                "without persistent object storage for uploaded "
                "documents."
            )

        run_alembic_upgrade()
    else:
        # Local development: create_all for brand-new tables.
        Base.metadata.create_all(bind=engine)

    # Safety net on every startup, in both modes: patches any column
    # added to a model after its table already existed — e.g. a
    # database that predates a migration, or one whose tables were
    # created by an earlier create_all before a column existed. Runs on
    # any dialect (see database/migrate.py) so this now also covers
    # Postgres, not just the SQLite databases it originally targeted.
    ensure_document_page_columns(engine)
    ensure_documents_columns(engine)
    ensure_document_metadata_field_columns(engine)
    ensure_extraction_model_columns(engine)

    _recover_interrupted_jobs()


def _recover_interrupted_jobs() -> None:
    """In-process background tasks don't survive a process restart —
    anything still queued/processing when the process died is stuck
    forever otherwise. Surface it as a clean failure instead."""

    from datetime import datetime, timezone

    from app.database.session import SessionLocal
    from app.models.extraction_job import ExtractionJob

    database = SessionLocal()

    try:
        stuck_jobs = database.query(ExtractionJob).filter(
            ExtractionJob.status.in_(["queued", "processing"])
        )

        for job in stuck_jobs:
            job.status = "failed"
            job.error_message = "Interrupted by a server restart."
            job.completed_at = datetime.now(timezone.utc)

        database.commit()
    finally:
        database.close()


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "application": settings.app_name,
        "status": "running",
        "mode": "oracle-dry-run",
    }


@app.get("/health")
async def health_check() -> dict[str, object]:
    provider = (settings.ai_provider or "").strip().lower()
    fallback_enabled = bool(settings.ai_fallback_enabled)
    provider_mode = (
        settings.ai_provider_mode or "development"
    ).strip().lower()

    # Development free-tier Gemini should show a privacy notice in the UI.
    show_dev_ai_warning = (
        fallback_enabled
        and provider == "gemini"
        and provider_mode == "development"
    )

    documents_via_convera = (
        settings.convera_enabled
        and settings.convera_documents_enabled
    )
    ai_via_convera = (
        settings.convera_enabled
        and settings.convera_ai_enabled
    )

    return {
        "status": "healthy",
        "environment": settings.app_env,
        "oracle_dry_run": settings.oracle_dry_run,
        "convera": {
            "enabled": settings.convera_enabled,
            "documents": (
                "convera" if documents_via_convera else "local"
            ),
            "ai": (
                "convera"
                if ai_via_convera
                else provider or "disabled"
            ),
            "migration_mode": (
                documents_via_convera and not ai_via_convera
            ),
        },
        "ai": {
            "provider": provider or "disabled",
            "fallback_enabled": fallback_enabled,
            "mode": provider_mode,
            "show_dev_warning": show_dev_ai_warning,
            "model": (
                settings.gemini_model
                if provider == "gemini"
                else None
            ),
        },
    }