import asyncio
from types import SimpleNamespace
from typing import Any

from app.schemas.document_target import DocumentTarget
from app.services.ai_provider import AIProvider, DisabledAIProvider
from app.services.semantic_schema_enrichment import (
    enrich_targets_semantically,
    needs_semantic_enrichment,
)


def _target(**overrides) -> DocumentTarget:
    defaults = {
        "id": "doc:obscure_field",
        "key": "obscure_field",
        "label": "obscure field",
        "display_name": "obscure field",
        "target_type": "field",
        "page_numbers": [1],
        "confidence": 0.8,
        "source_examples": ["'obscure field: X' on page 1 (inline_regex)"],
        "group": "Document Fields",
        "value_type": "string",
    }
    defaults.update(overrides)
    return DocumentTarget(**defaults)


class StubEnrichingProvider(AIProvider):
    provider_id = "stub"

    async def extract(self, *, instruction: str, page_context: str) -> dict[str, Any]:
        return {"values": [], "warnings": []}

    async def classify(self, *, page_context: str) -> dict[str, Any]:
        return {"document_type": "Other", "confidence": 0.0}

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

    async def enrich_schema(
        self, *, targets_json: str, page_context: str
    ) -> dict[str, Any]:
        return {
            "enrichments": [
                {
                    "key": "obscure_field",
                    "display_name": "Termination Notice Period",
                    "group": "Dates",
                    "value_type": "string",
                    "description": "How much notice is required to terminate.",
                }
            ],
            "warnings": [],
        }


def test_needs_semantic_enrichment_for_generic_group() -> None:
    assert needs_semantic_enrichment(_target()) is True
    assert (
        needs_semantic_enrichment(
            _target(
                group="Identifiers",
                display_name="Contract Number",
                label="Contract Number",
                key="contract_number",
                discovery_method="inline_regex",
                description="Contract identifier",
            )
        )
        is False
    )


def test_enrich_targets_applies_display_and_group() -> None:
    pages = [
        SimpleNamespace(
            page_number=1,
            final_text="Termination notice: 30 days",
            form_fields_json={},
            tables_json=[],
        )
    ]
    targets = [_target()]
    enriched, warnings = asyncio.run(
        enrich_targets_semantically(
            targets=targets,
            pages=pages,
            ai_provider=StubEnrichingProvider(),
        )
    )
    assert warnings == []
    assert enriched[0].display_name == "Termination Notice Period"
    assert enriched[0].group == "Dates"
    assert enriched[0].key == "obscure_field"  # keys never change
    assert "semantic" in (enriched[0].discovery_method or "")


def test_enrich_targets_noop_when_ai_disabled() -> None:
    targets = [_target()]
    enriched, warnings = asyncio.run(
        enrich_targets_semantically(
            targets=targets,
            pages=[],
            ai_provider=DisabledAIProvider(),
        )
    )
    assert enriched[0].display_name == "obscure field"
    assert warnings == []
