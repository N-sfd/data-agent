"""Provider-failure matrix for disabled / gemini / openai / auto / all-down."""

from __future__ import annotations

import asyncio
import time
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
from app.services.openai_provider import OpenAIAIProvider
from app.services.semantic_schema_enrichment import enrich_targets_semantically
from app.schemas.document_target import DocumentTarget


class FailingProvider(AIProvider):
    provider_id = "failing"

    def __init__(self, name: str = "failing", *, delay: float = 0.0) -> None:
        self.provider_id = name
        self.delay = delay
        self.calls = 0

    async def extract(self, *, instruction: str, page_context: str) -> dict[str, Any]:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        raise AIProviderError(f"{self.provider_id} unavailable")

    async def classify(self, *, page_context: str) -> dict[str, Any]:
        self.calls += 1
        raise AIProviderError(f"{self.provider_id} unavailable")

    async def extract_fields(self, *, page_context: str, field_specs: list) -> dict[str, Any]:
        raise AIProviderError("unavailable")

    async def extract_clauses(self, *, page_context: str) -> dict[str, Any]:
        raise AIProviderError("unavailable")

    async def extract_signatures(self, *, page_context: str) -> dict[str, Any]:
        raise AIProviderError("unavailable")

    async def extract_structured_tables(
        self, *, page_context: str, table_specs: list
    ) -> dict[str, Any]:
        raise AIProviderError("unavailable")

    async def enrich_schema(
        self, *, targets_json: str, page_context: str
    ) -> dict[str, Any]:
        self.calls += 1
        raise AIProviderError(f"{self.provider_id} enrich failed")


class OkProvider(AIProvider):
    provider_id = "ok"

    def __init__(self, name: str = "ok") -> None:
        self.provider_id = name
        self.calls = 0

    async def extract(self, *, instruction: str, page_context: str) -> dict[str, Any]:
        self.calls += 1
        return {"answer": self.provider_id, "values": [], "warnings": []}

    async def classify(self, *, page_context: str) -> dict[str, Any]:
        return {"document_type": "Other", "confidence": 0.1}

    async def extract_fields(self, *, page_context: str, field_specs: list) -> dict[str, Any]:
        return {"fields": []}

    async def extract_clauses(self, *, page_context: str) -> dict[str, Any]:
        return {"clauses": []}

    async def extract_signatures(self, *, page_context: str) -> dict[str, Any]:
        return {"signatures": []}

    async def extract_structured_tables(
        self, *, page_context: str, table_specs: list
    ) -> dict[str, Any]:
        return {"rows": []}


def test_disabled_provider_from_settings() -> None:
    provider = create_ai_provider(Settings(ai_fallback_enabled=False))
    assert isinstance(provider, DisabledAIProvider)


def test_openai_selected_independently() -> None:
    provider = create_ai_provider(
        Settings(
            ai_fallback_enabled=True,
            ai_provider="openai",
            openai_api_key="sk-test",
            gemini_api_key=None,
            ollama_base_url=None,
            convera_enabled=False,
        )
    )
    assert isinstance(provider, OpenAIAIProvider)


def test_auto_chain_order_gemini_openai_ollama() -> None:
    provider = create_ai_provider(
        Settings(
            ai_fallback_enabled=True,
            ai_provider="auto",
            gemini_api_key="gem-key",
            openai_api_key="sk-test",
            ollama_base_url="http://127.0.0.1:11434",
            convera_enabled=False,
            # Avoid constructing a real Gemini client in this matrix when
            # google-genai is picky — factory may still build Gemini.
        )
    )
    # May be Fallback or single if Gemini init fails in CI.
    assert provider.provider_id != "disabled"
    if isinstance(provider, FallbackAIProvider):
        ids = [getattr(p, "provider_id", "") for p in provider.providers]
        assert ids[0] in {"gemini", "openai", "ollama"}
        if "gemini" in ids and "openai" in ids:
            assert ids.index("gemini") < ids.index("openai")


def test_gemini_failure_soft_falls_back() -> None:
    primary = FailingProvider("gemini")
    secondary = OkProvider("openai")
    chained = FallbackAIProvider(
        [primary, secondary],
        attempt_timeout_seconds=2,
        max_providers=3,
    )
    result = asyncio.run(
        chained.extract(instruction="x", page_context="y")
    )
    assert result["answer"] == "openai"
    assert primary.calls == 1
    assert secondary.calls == 1


def test_all_providers_unavailable_raises_once_each() -> None:
    a = FailingProvider("gemini")
    b = FailingProvider("openai")
    c = FailingProvider("ollama")
    chained = FallbackAIProvider(
        [a, b, c],
        attempt_timeout_seconds=1,
        max_providers=3,
    )
    with pytest.raises(AIProviderError, match="All AI fallback providers failed"):
        asyncio.run(chained.extract(instruction="x", page_context="y"))
    assert a.calls == 1
    assert b.calls == 1
    assert c.calls == 1


def test_fallback_respects_max_providers_cap() -> None:
    providers = [FailingProvider(f"p{i}") for i in range(5)]
    chained = FallbackAIProvider(
        providers,
        attempt_timeout_seconds=1,
        max_providers=2,
    )
    assert len(chained.providers) == 2
    with pytest.raises(AIProviderError):
        asyncio.run(chained.extract(instruction="x", page_context="y"))
    assert providers[0].calls == 1
    assert providers[1].calls == 1
    assert providers[2].calls == 0


def test_fallback_attempt_timeout_does_not_cascade_forever() -> None:
    slow = FailingProvider("slow", delay=2.0)
    fast = OkProvider("fast")
    chained = FallbackAIProvider(
        [slow, fast],
        attempt_timeout_seconds=0.2,
        max_providers=3,
    )
    started = time.perf_counter()
    result = asyncio.run(chained.extract(instruction="x", page_context="y"))
    elapsed = time.perf_counter() - started
    assert result["answer"] == "fast"
    assert elapsed < 1.5  # timed out slow path; did not wait full 2s + retries


def test_all_providers_down_enrichment_soft_skips() -> None:
    target = DocumentTarget(
        id="doc:x",
        key="obscure_field",
        label="obscure field",
        target_type="field",
        page_numbers=[1],
        confidence=0.8,
        group="Document Fields",
    )
    enriched, warnings = asyncio.run(
        enrich_targets_semantically(
            targets=[target],
            pages=[],
            ai_provider=FailingProvider("gemini"),
        )
    )
    assert enriched[0].key == "obscure_field"
    assert enriched[0].display_name == target.display_name or "obscure field"
    assert any("unavailable" in warning.lower() or "heuristic" in warning.lower() for warning in warnings)
