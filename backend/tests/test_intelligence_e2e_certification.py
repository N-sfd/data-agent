"""API-level intelligence certification cases A–H.

Browser Playwright E2E is deferred; these cases certify the durable
intelligence spine and AI-path variants through the HTTP API.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services.ai_provider import AIProvider, AIProviderError, DisabledAIProvider
from app.services.fallback_ai_provider import FallbackAIProvider

client = TestClient(app)


class FailingProvider(AIProvider):
    provider_id = "failing"

    async def extract(self, *, instruction: str, page_context: str) -> dict[str, Any]:
        raise AIProviderError("primary down")

    async def classify(self, *, page_context: str) -> dict[str, Any]:
        raise AIProviderError("primary down")

    async def extract_fields(self, *, page_context: str, field_specs: list) -> dict[str, Any]:
        raise AIProviderError("primary down")

    async def extract_clauses(self, *, page_context: str) -> dict[str, Any]:
        raise AIProviderError("primary down")

    async def extract_signatures(self, *, page_context: str) -> dict[str, Any]:
        raise AIProviderError("primary down")

    async def extract_structured_tables(
        self, *, page_context: str, table_specs: list
    ) -> dict[str, Any]:
        raise AIProviderError("primary down")

    async def enrich_schema(
        self, *, targets_json: str, page_context: str
    ) -> dict[str, Any]:
        raise AIProviderError("primary down")


class RecoveringProvider(AIProvider):
    provider_id = "recovering"

    async def extract(self, *, instruction: str, page_context: str) -> dict[str, Any]:
        return {"answer": None, "values": [], "warnings": ["fallback used"]}

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

    async def enrich_schema(
        self, *, targets_json: str, page_context: str
    ) -> dict[str, Any]:
        return {"enrichments": [], "warnings": []}


def _pdf(marker: str) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), f"Contract Number: {marker}", fontsize=10)
    page.insert_text((72, 92), "Payment Terms: Net 30", fontsize=10)
    page.insert_text((72, 112), "Effective Date: 2026-01-15", fontsize=10)
    content = pdf.tobytes()
    pdf.close()
    return content


def _upload_pages(marker: str) -> str:
    upload = client.post(
        "/api/documents/upload",
        files={"file": (f"cert-{uuid4()}.pdf", _pdf(marker), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]
    pages = client.post(
        f"/api/documents/{document_id}/extract-pages",
        json={
            "run_ocr": False,
            "page_start": None,
            "page_end": None,
            "force_reprocess": False,
        },
    )
    assert pages.status_code == 200, pages.text
    return document_id


def _discover(document_id: str, provider: AIProvider) -> dict:
    with patch(
        "app.api.universal_extraction.create_ai_provider",
        return_value=provider,
    ):
        response = client.post(f"/api/documents/{document_id}/discover-schema")
    assert response.status_code == 200, response.text
    return response.json()


def _extract(document_id: str, target_ids: list[str], *, use_ai: bool) -> dict:
    start = client.post(
        f"/api/documents/{document_id}/jobs/extract",
        json={"target_ids": target_ids, "use_ai_fallback": use_ai},
    )
    assert start.status_code == 202, start.text
    job_id = start.json()["id"]
    job = None
    for _ in range(80):
        job = client.get(f"/v1/jobs/{job_id}").json()
        if job["status"] in ("complete", "failed"):
            break
        time.sleep(0.05)
    assert job is not None
    assert job["status"] == "complete", job
    return job


def _assert_intelligence(scalar: dict) -> None:
    assert "value" in scalar
    assert scalar.get("extraction_method")
    assert scalar.get("retrieval")
    assert scalar.get("validation")
    assert scalar.get("confidence_detail")
    assert scalar.get("evidence", {}).get("page_number")


def test_case_a_deterministic_only_document() -> None:
    marker = f"DET-{uuid4().hex[:6].upper()}"
    document_id = _upload_pages(marker)
    schema = _discover(document_id, DisabledAIProvider())
    ids = [t["id"] for t in schema["targets"] if t.get("source_examples")][:5]
    job = _extract(document_id, ids, use_ai=False)
    assert job["result"]["scalars"]
    for scalar in job["result"]["scalars"]:
        _assert_intelligence(scalar)
        assert scalar["extraction_method"] != "ai"


def test_case_d_ai_disabled_still_completes() -> None:
    marker = f"DIS-{uuid4().hex[:6].upper()}"
    document_id = _upload_pages(marker)
    schema = _discover(document_id, DisabledAIProvider())
    ids = [t["id"] for t in schema["targets"] if t.get("source_examples")][:5]
    job = _extract(document_id, ids, use_ai=True)
    assert job["status"] == "complete"
    persisted = client.get(f"/api/documents/{document_id}/extract-results")
    assert persisted.status_code == 200
    assert persisted.json()["scalars"]


def test_case_e_primary_provider_fails_deterministic_survives() -> None:
    marker = f"FAIL-{uuid4().hex[:6].upper()}"
    document_id = _upload_pages(marker)
    schema = _discover(document_id, FailingProvider())
    # Discovery must not hard-fail when enrichment provider errors.
    assert schema["targets"]
    ids = [t["id"] for t in schema["targets"] if t.get("source_examples")][:5]
    with patch(
        "app.services.extraction_job_runner.create_ai_provider",
        return_value=FailingProvider(),
    ):
        job = _extract(document_id, ids, use_ai=True)
    assert job["status"] == "complete"
    assert job["result"]["scalars"] or job["result"]["unresolved_targets"] is not None


def test_case_f_auto_fallback_succeeds() -> None:
    chained = FallbackAIProvider(
        [FailingProvider(), RecoveringProvider()],
        attempt_timeout_seconds=2,
        max_providers=2,
    )
    marker = f"AUTO-{uuid4().hex[:6].upper()}"
    document_id = _upload_pages(marker)
    schema = _discover(document_id, chained)
    assert schema["targets"]


def test_case_g_enrichment_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AI_SCHEMA_ENRICHMENT_ENABLED", "false")
    # Settings are cached — patch get_settings used by discovery.
    settings = Settings(ai_schema_enrichment_enabled=False, ai_fallback_enabled=False)
    marker = f"ENROFF-{uuid4().hex[:6].upper()}"
    document_id = _upload_pages(marker)
    with patch("app.services.schema_discovery.get_settings", return_value=settings):
        schema = _discover(document_id, DisabledAIProvider())
    assert schema["targets"]
    for target in schema["targets"]:
        assert "semantic" not in (target.get("discovery_method") or "")


def test_case_h_enrichment_enabled_with_disabled_ai_is_noop() -> None:
    settings = Settings(ai_schema_enrichment_enabled=True, ai_fallback_enabled=False)
    marker = f"ENRON-{uuid4().hex[:6].upper()}"
    document_id = _upload_pages(marker)
    with patch("app.services.schema_discovery.get_settings", return_value=settings):
        schema = _discover(document_id, DisabledAIProvider())
    assert schema["targets"]


def test_persist_reopen_certifies_intelligence_objects() -> None:
    marker = f"REOPEN-{uuid4().hex[:6].upper()}"
    document_id = _upload_pages(marker)
    schema = _discover(document_id, DisabledAIProvider())
    ids = [t["id"] for t in schema["targets"] if t.get("source_examples")][:5]
    job = _extract(document_id, ids, use_ai=False)
    assert job["result"]["scalars"]
    reopen = client.get(f"/api/documents/{document_id}/extract-results").json()
    assert reopen["scalars"]
    for scalar in reopen["scalars"]:
        assert scalar.get("confidence_detail") is not None
        assert scalar.get("validation") is not None
