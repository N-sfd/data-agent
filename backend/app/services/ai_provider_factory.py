from app.core.config import Settings
from app.services.ai_provider import (
    AIProvider,
    DisabledAIProvider,
)
from app.services.convera_ai_provider import (
    ConveraAIProvider,
)


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

    provider = (
        (settings.ai_provider or "")
        .strip()
        .lower()
    )

    if provider == "gemini":
        from app.services.gemini_provider import GeminiAIProvider

        api_key = (
            settings.gemini_api_key or ""
        ).strip()

        if (
            not api_key
            or api_key.lower()
            in {"your_key_here", "replace-me"}
        ):
            return DisabledAIProvider()

        return GeminiAIProvider(
            api_key=api_key,
            model=settings.gemini_model,
        )

    return DisabledAIProvider()
