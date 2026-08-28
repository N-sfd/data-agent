import asyncio
from typing import Any

import pytest

from app.core.config import Settings
from app.services.ai_provider import (
    AIProvider,
    AIProviderError,
    DisabledAIProvider,
)
from app.services.ai_provider_factory import create_ai_provider
from app.services.fallback_ai_provider import FallbackAIProvider


class FailingProvider(AIProvider):
    async def extract(self, *, instruction: str, page_context: str) -> dict[str, Any]:
        raise AIProviderError("Primary provider rate limit exceeded (HTTP 429)")

    async def classify(self, *, page_context: str) -> dict[str, Any]:
        raise AIProviderError("Primary classification failure")

    async def extract_fields(self, *, page_context: str, field_specs: list) -> dict[str, Any]:
        raise AIProviderError("Primary field extraction failure")

    async def extract_clauses(self, *, page_context: str) -> dict[str, Any]:
        raise AIProviderError("Primary clause extraction failure")

    async def extract_signatures(self, *, page_context: str) -> dict[str, Any]:
        raise AIProviderError("Primary signature extraction failure")

    async def extract_structured_tables(self, *, page_context: str, table_specs: list) -> dict[str, Any]:
        raise AIProviderError("Primary structured table failure")


class SuccessfulFallbackProvider(AIProvider):
    async def extract(self, *, instruction: str, page_context: str) -> dict[str, Any]:
        return {"answer": "Extracted via Ollama local fallback", "values": [], "warnings": []}

    async def classify(self, *, page_context: str) -> dict[str, Any]:
        return {"document_type": "Contract", "industry": "Defense", "contract_side": "sell", "language": "en", "confidence": 0.9}

    async def extract_fields(self, *, page_context: str, field_specs: list) -> dict[str, Any]:
        return {"fields": [{"field_name": "contract_number", "value": "W912HQ-24-C-0001", "confidence": 0.95}]}

    async def extract_clauses(self, *, page_context: str) -> dict[str, Any]:
        return {"clauses": []}

    async def extract_signatures(self, *, page_context: str) -> dict[str, Any]:
        return {"signatures": []}

    async def extract_structured_tables(self, *, page_context: str, table_specs: list) -> dict[str, Any]:
        return {"tables": []}


def test_fallback_provider_switches_when_primary_fails():
    primary = FailingProvider()
    fallback = SuccessfulFallbackProvider()
    chained = FallbackAIProvider([primary, fallback])

    res = asyncio.run(
        chained.extract(
            instruction="Extract contract number",
            page_context="Sample contract text",
        )
    )
    assert res["answer"] == "Extracted via Ollama local fallback"

    cls_res = asyncio.run(
        chained.classify(
            page_context="Sample contract text",
        )
    )
    assert cls_res["document_type"] == "Contract"


def test_ai_provider_factory_disabled():
    settings = Settings(ai_fallback_enabled=False)
    provider = create_ai_provider(settings)
    assert isinstance(provider, DisabledAIProvider)
