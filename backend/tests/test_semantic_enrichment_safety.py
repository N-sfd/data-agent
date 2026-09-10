"""Semantic enrichment safety: keys stable, adversarial suggestions rejected."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from app.schemas.document_target import DocumentTarget
from app.services.ai_provider import AIProvider, AIProviderError, DisabledAIProvider
from app.services.semantic_schema_enrichment import (
    enrich_targets_semantically,
    needs_semantic_enrichment,
)


def _page() -> SimpleNamespace:
    return SimpleNamespace(
        page_number=1,
        final_text="obscure field: 30 days",
        form_fields_json={},
        tables_json=[],
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
        "source_examples": [],
        "group": "Document Fields",
        "value_type": "string",
        "discovery_method": "inline_regex",
    }
    defaults.update(overrides)
    return DocumentTarget(**defaults)


class ScriptedEnrichProvider(AIProvider):
    provider_id = "scripted"

    def __init__(self, enrichments: list[dict], *, fail: bool = False) -> None:
        self.enrichments = enrichments
        self.fail = fail

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
        if self.fail:
            raise AIProviderError("enrichment offline")
        return {"enrichments": self.enrichments, "warnings": []}


def _run(targets, enrichments=None, fail=False):
    return asyncio.run(
        enrich_targets_semantically(
            targets=targets,
            pages=[_page()],
            ai_provider=ScriptedEnrichProvider(enrichments or [], fail=fail),
        )
    )


def test_display_name_only_change() -> None:
    target = _target()
    enriched, _ = _run(
        [target],
        [{"key": "obscure_field", "display_name": "Notice Period"}],
    )
    assert enriched[0].key == "obscure_field"
    assert enriched[0].display_name == "Notice Period"
    assert enriched[0].group == "Document Fields"


def test_group_only_change() -> None:
    target = _target()
    enriched, _ = _run(
        [target],
        [{"key": "obscure_field", "group": "Dates"}],
    )
    assert enriched[0].key == "obscure_field"
    assert enriched[0].group == "Dates"
    assert enriched[0].display_name == "obscure field"


def test_value_type_only_change() -> None:
    target = _target()
    enriched, _ = _run(
        [target],
        [{"key": "obscure_field", "value_type": "date"}],
    )
    assert enriched[0].key == "obscure_field"
    assert enriched[0].value_type == "date"


def test_ai_cannot_rename_key() -> None:
    target = _target()
    enriched, _ = _run(
        [target],
        [
            {
                "key": "brand_new_key",
                "display_name": "Hijacked",
                "group": "Dates",
            },
            {
                "key": "obscure_field",
                "display_name": "Safe Name",
            },
        ],
    )
    keys = {item.key for item in enriched}
    assert keys == {"obscure_field"}
    assert enriched[0].display_name == "Safe Name"


def test_duplicate_enrichment_entries_dedupe() -> None:
    target = _target()
    enriched, _ = _run(
        [target],
        [
            {"key": "obscure_field", "display_name": "First"},
            {"key": "obscure_field", "display_name": "Second"},
        ],
    )
    assert enriched[0].display_name == "First"


def test_internal_xfa_enrichment_rejected() -> None:
    target = _target()
    enriched, _ = _run(
        [target],
        [
            {
                "key": "topmostSubform[0].Page1[0].ContractNumber[0]",
                "display_name": "Should Not Appear",
            },
            {
                "key": "obscure_field",
                "display_name": "topmostSubform.ContractNumber",
            },
        ],
    )
    assert len(enriched) == 1
    assert enriched[0].key == "obscure_field"
    # Internal-looking display names are rejected.
    assert enriched[0].display_name == "obscure field"


def test_ai_failure_keeps_heuristic_schema() -> None:
    target = _target(display_name="Heuristic Label", label="Heuristic Label")
    enriched, warnings = _run([target], fail=True)
    assert enriched[0].display_name == "Heuristic Label"
    assert enriched[0].key == "obscure_field"
    assert warnings


def test_well_defined_targets_are_not_enriched() -> None:
    target = _target(
        key="contract_number",
        label="Contract Number",
        display_name="Contract Number",
        group="Identifiers",
        discovery_method="inline_regex",
        description="Contract identifier",
    )
    assert needs_semantic_enrichment(target) is False
    enriched, _ = _run(
        [target],
        [{"key": "contract_number", "display_name": "Should Not Apply", "group": "Other"}],
    )
    assert enriched[0].display_name == "Contract Number"
    assert enriched[0].group == "Identifiers"


def test_disabled_provider_is_noop() -> None:
    target = _target()
    enriched, warnings = asyncio.run(
        enrich_targets_semantically(
            targets=[target],
            pages=[_page()],
            ai_provider=DisabledAIProvider(),
        )
    )
    assert enriched[0].display_name == "obscure field"
    assert warnings == []
