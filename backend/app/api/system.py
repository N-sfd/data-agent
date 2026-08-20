from fastapi import APIRouter

from app.core.config import get_settings
from app.services.convera_client import ConveraClient, ConveraError
from app.services.document_provider import should_use_convera_documents


router = APIRouter(
    tags=["System"],
)
settings = get_settings()


@router.get("/convera-status")
def convera_status() -> dict:
    documents_via_convera = should_use_convera_documents(settings)
    ai_via_convera = (
        settings.convera_enabled
        and settings.convera_ai_enabled
    )

    if not settings.convera_enabled:
        return {
            "enabled": False,
            "connected": False,
            "documents": "local",
            "ai": settings.ai_provider or "disabled",
            "migration_mode": False,
        }

    try:
        client = ConveraClient()
        health = client.health()

        return {
            "enabled": True,
            "connected": True,
            "url": client.base_url,
            "health": health,
            "documents": (
                "convera" if documents_via_convera else "local"
            ),
            "ai": (
                "convera"
                if ai_via_convera
                else settings.ai_provider or "disabled"
            ),
            "migration_mode": (
                documents_via_convera and not ai_via_convera
            ),
            "flags": {
                "convera_documents_enabled": (
                    settings.convera_documents_enabled
                ),
                "convera_ai_enabled": settings.convera_ai_enabled,
            },
        }

    except (ConveraError, RuntimeError) as exc:
        return {
            "enabled": True,
            "connected": False,
            "error": str(exc),
            "documents": (
                "convera" if documents_via_convera else "local"
            ),
            "ai": (
                "convera"
                if ai_via_convera
                else settings.ai_provider or "disabled"
            ),
            "migration_mode": (
                documents_via_convera and not ai_via_convera
            ),
            "flags": {
                "convera_documents_enabled": (
                    settings.convera_documents_enabled
                ),
                "convera_ai_enabled": settings.convera_ai_enabled,
            },
        }
