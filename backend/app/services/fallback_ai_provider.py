import logging
from typing import Any

from app.services.ai_provider import (
    AIProvider,
    AIProviderError,
)
from app.services.contract_field_schema import FieldSpec
from app.services.contract_structured_table_schema import StructuredTableSpec

logger = logging.getLogger(__name__)


class FallbackAIProvider(AIProvider):
    """
    Chains multiple AI providers together (e.g. Gemini -> Ollama).
    If the primary provider encounters an error, rate limit, or timeout,
    execution seamlessly falls back to the secondary provider.
    """

    def __init__(
        self,
        providers: list[AIProvider],
    ) -> None:
        self.providers = [p for p in providers if p is not None]
        if not self.providers:
            raise ValueError("FallbackAIProvider requires at least one provider.")

    async def _execute_with_fallback(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        errors: list[str] = []

        for idx, provider in enumerate(self.providers):
            provider_name = getattr(
                provider, "__class__", type(provider)
            ).__name__
            try:
                method = getattr(provider, method_name)
                result = await method(*args, **kwargs)
                if idx > 0:
                    logger.info(
                        "Fallback provider %s succeeded for %s after prior failures.",
                        provider_name,
                        method_name,
                    )
                return result
            except (AIProviderError, Exception) as exc:
                err_msg = f"{provider_name}.{method_name} failed: {exc}"
                logger.warning(err_msg)
                errors.append(err_msg)

        raise AIProviderError(
            f"All AI fallback providers failed for {method_name}: {'; '.join(errors)}"
        )

    async def extract(
        self,
        *,
        instruction: str,
        page_context: str,
    ) -> dict[str, Any]:
        return await self._execute_with_fallback(
            "extract",
            instruction=instruction,
            page_context=page_context,
        )

    async def classify(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:
        return await self._execute_with_fallback(
            "classify",
            page_context=page_context,
        )

    async def extract_fields(
        self,
        *,
        page_context: str,
        field_specs: list[FieldSpec],
    ) -> dict[str, Any]:
        return await self._execute_with_fallback(
            "extract_fields",
            page_context=page_context,
            field_specs=field_specs,
        )

    async def extract_clauses(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:
        return await self._execute_with_fallback(
            "extract_clauses",
            page_context=page_context,
        )

    async def extract_signatures(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:
        return await self._execute_with_fallback(
            "extract_signatures",
            page_context=page_context,
        )

    async def extract_structured_tables(
        self,
        *,
        page_context: str,
        table_specs: list[StructuredTableSpec],
    ) -> dict[str, Any]:
        return await self._execute_with_fallback(
            "extract_structured_tables",
            page_context=page_context,
            table_specs=table_specs,
        )
