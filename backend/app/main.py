from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    contract_analysis,
    dashboard,
    documents,
    extraction_models,
    financial_analysis,
    page_extraction,
    universal_extraction,
)
from app.core.config import get_settings
from app.database.base import Base
from app.database.migrate import (
    ensure_document_metadata_field_columns,
    ensure_document_page_columns,
    ensure_documents_columns,
)
from app.database.session import engine
from app.models import document as document_model  # noqa: F401
from app.models import document_clause as document_clause_model  # noqa: F401
from app.models import (  # noqa: F401
    document_metadata_field as document_metadata_field_model,
)
from app.models import document_page as document_page_model  # noqa: F401
from app.models import (  # noqa: F401
    document_signature as document_signature_model,
)
from app.models import (  # noqa: F401
    extraction_model as extraction_model_model,
)
from app.models import (  # noqa: F401
    metadata_field_audit_log as metadata_field_audit_log_model,
)
from app.models import page_text_block as page_text_block_model  # noqa: F401

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


@app.on_event("startup")
async def create_database_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_document_page_columns(engine)
    ensure_documents_columns(engine)
    ensure_document_metadata_field_columns(engine)


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

    return {
        "status": "healthy",
        "environment": settings.app_env,
        "oracle_dry_run": settings.oracle_dry_run,
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