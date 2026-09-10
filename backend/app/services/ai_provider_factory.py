"""Build the configured AIProvider without callers knowing vendor details."""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.ai_provider import AIProvider, DisabledAIProvider
from app.services.convera_ai_provider import ConveraAIProvider
from app.services.fallback_ai_provider import FallbackAIProvider
from app.services.ollama_provider import OllamaAIProvider

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = {"", "your_key_here", "replace-me", "changeme"}


def _clean_key(value: str | None) -> str | None:
    key = (value or "").strip()
    if not key or key.lower() in _PLACEHOLDER_KEYS:
        return None
    return key


def _build_gemini(settings: Settings) -> AIProvider | None:
    api_key = _clean_key(settings.gemini_api_key)
    if not api_key:
        return None
    try:
        from app.services.gemini_provider import GeminiAIProvider

        return GeminiAIProvider(api_key=api_key, model=settings.gemini_model)
    except Exception as exc:
        logger.warning("Failed to initialize Gemini AI provider: %s", exc)
        return None


def _build_openai(settings: Settings) -> AIProvider | None:
    api_key = _clean_key(settings.openai_api_key)
    if not api_key:
        return None
    try:
        from app.services.openai_provider import OpenAIAIProvider

        return OpenAIAIProvider(
            api_key=api_key,
            model=settings.openai_model or "gpt-4o-mini",
        )
    except Exception as exc:
        logger.warning("Failed to initialize OpenAI provider: %s", exc)
        return None


def _build_ollama(settings: Settings) -> AIProvider | None:
    base_url = (settings.ollama_base_url or "").strip()
    if not base_url:
        return None
    try:
        return OllamaAIProvider(
            base_url=base_url,
            model=settings.ollama_model,
        )
    except Exception as exc:
        logger.warning("Failed to initialize Ollama provider: %s", exc)
        return None


def _chain(providers: list[AIProvider], settings: Settings) -> AIProvider:
    usable = [provider for provider in providers if provider is not None]
    if not usable:
        return DisabledAIProvider()
    if len(usable) == 1:
        return usable[0]
    return FallbackAIProvider(
        usable,
        attempt_timeout_seconds=settings.ai_provider_attempt_timeout_seconds,
        max_providers=settings.ai_fallback_max_providers,
    )


def create_ai_provider(settings: Settings) -> AIProvider:
    """Resolve the active provider (or fallback chain) from settings."""

    if not settings.ai_fallback_enabled:
        return DisabledAIProvider()

    if settings.convera_enabled and settings.convera_ai_enabled:
        api_key = _clean_key(settings.convera_api_key)
        if not api_key:
            return DisabledAIProvider()
        return ConveraAIProvider(
            api_url=settings.convera_api_url,
            api_key=api_key,
        )

    name = (settings.ai_provider or "auto").strip().lower()

    if name == "ollama":
        return _build_ollama(settings) or DisabledAIProvider()

    if name == "openai":
        return _build_openai(settings) or DisabledAIProvider()

    if name == "gemini":
        return _build_gemini(settings) or DisabledAIProvider()

    if name in {"auto", "gemini_fallback", ""}:
        # Prefer cloud primary, then optional OpenAI, then local Ollama.
        return _chain(
            [
                provider
                for provider in (
                    _build_gemini(settings),
                    _build_openai(settings),
                    _build_ollama(settings),
                )
                if provider is not None
            ],
            settings,
        )

    logger.warning("Unknown ai_provider=%r; falling back to auto chain.", name)
    return _chain(
        [
            provider
            for provider in (
                _build_gemini(settings),
                _build_openai(settings),
                _build_ollama(settings),
            )
            if provider is not None
        ],
        settings,
    )


def describe_ai_provider(provider: AIProvider) -> str:
    """Human-readable id for logs / notices."""

    if isinstance(provider, FallbackAIProvider):
        parts = [
            getattr(item, "provider_id", item.__class__.__name__)
            for item in provider.providers
        ]
        return "fallback(" + "+".join(parts) + ")"
    return getattr(provider, "provider_id", provider.__class__.__name__)
