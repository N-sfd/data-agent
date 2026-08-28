import logging

from app.core.config import Settings
from app.services.ai_provider import (
    AIProvider,
    DisabledAIProvider,
)
from app.services.convera_ai_provider import (
    ConveraAIProvider,
)
from app.services.fallback_ai_provider import FallbackAIProvider
from app.services.ollama_provider import OllamaAIProvider

logger = logging.getLogger(__name__)


def create_ai_provider(
    settings: Settings,
) -> AIProvider:
    if not settings.ai_fallback_enabled:
        return DisabledAIProvider()

    if settings.convera_enabled and settings.convera_ai_enabled:
        api_key = (settings.convera_api_key or "").strip()
        if not api_key:
            return DisabledAIProvider()

        return ConveraAIProvider(
            api_url=settings.convera_api_url,
            api_key=api_key,
        )

    provider = (settings.ai_provider or "").strip().lower()

    if provider == "ollama":
        return OllamaAIProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )

    providers: list[AIProvider] = []

    # 1. Primary: Gemini (if configured)
    if provider in {"gemini", "auto", "gemini_fallback", ""}:
        api_key = (settings.gemini_api_key or "").strip()
        if api_key and api_key.lower() not in {"your_key_here", "replace-me"}:
            try:
                from app.services.gemini_provider import GeminiAIProvider

                providers.append(
                    GeminiAIProvider(
                        api_key=api_key,
                        model=settings.gemini_model,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to initialize Gemini AI provider: %s", exc)

    # 2. Secondary: Ollama (local fallback if base_url is specified)
    if settings.ollama_base_url:
        try:
            providers.append(
                OllamaAIProvider(
                    base_url=settings.ollama_base_url,
                    model=settings.ollama_model,
                )
            )
        except Exception as exc:
            logger.warning("Failed to initialize Ollama fallback provider: %s", exc)

    if not providers:
        return DisabledAIProvider()

    if len(providers) == 1:
        return providers[0]

    return FallbackAIProvider(providers)

