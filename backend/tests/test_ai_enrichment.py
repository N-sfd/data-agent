"""AI is optional enrichment: deterministic extraction must complete — and
its results must stand unchanged — whatever the AI provider does."""

from __future__ import annotations

import asyncio
import time
from contextlib import ExitStack
from unittest.mock import patch
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_enrichment import (
    AIEnrichmentSession,
    classify_ai_error,
    start_session,
)
from app.services.ai_provider import AIProvider, AIProviderError, DisabledAIProvider
from app.services.ai_provider_factory import create_ai_provider
from app.services.extraction_job_runner import settings as runner_settings

client = TestClient(app)

QUOTA_429 = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota', "
    "'status': 'RESOURCE_EXHAUSTED', 'details': [{'violations': [{'quotaId': "
    "'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}, {'retryDelay': '40s'}]}}"
)


class FakeProvider(AIProvider):
    """A configured provider (not the disabled one) that counts calls;
    `behaviour` decides what each extract() does."""

    provider_id = "fake-gemini"

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    async def extract(self, *, instruction: str, page_context: str):
        self.calls += 1
        return await self.behaviour(self.calls, instruction, page_context)

    async def classify(self, *, page_context: str):
        return {"document_type": "Other", "confidence": 0.0}

    async def extract_fields(self, *, page_context: str, field_specs):
        return {"fields": []}

    async def extract_clauses(self, *, page_context: str):
        return {"clauses": []}

    async def extract_signatures(self, *, page_context: str):
        return {"signatures": []}

    async def extract_structured_tables(self, *, page_context: str, table_specs):
        return {"rows": []}


async def _quota(*_):
    raise RuntimeError(QUOTA_429)


# --- classification ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        (QUOTA_429, "quota"),
        ("429 RESOURCE_EXHAUSTED rate limit, retryDelay: '2s'", "rate_limited"),
        ("503 UNAVAILABLE. This model is currently experiencing high demand.", "provider_error"),
        ("400 INVALID_ARGUMENT API key not valid. Please pass a valid API key. API_KEY_INVALID", "auth"),
        ("httpx.ConnectError: getaddrinfo failed", "network"),
    ],
)
def test_provider_errors_are_classified(message, kind):
    assert classify_ai_error(RuntimeError(message)).kind == kind


def test_short_rate_limit_carries_its_retry_delay():
    failure = classify_ai_error(RuntimeError("429 RESOURCE_EXHAUSTED rate limit, retryDelay: '2s'"))
    assert failure.retry_after == 2.0 and not failure.terminal
    assert classify_ai_error(RuntimeError(QUOTA_429)).terminal
    assert classify_ai_error(asyncio.TimeoutError()).kind == "timeout"


# --- the session ------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def test_quota_exhaustion_opens_the_breaker_after_one_call():
    fake = FakeProvider(_quota)
    session = AIEnrichmentSession(provider=fake, provider_label="gemini", timeout_seconds=5)
    for _ in range(5):
        with pytest.raises(AIProviderError) as raised:
            _run(session.extract(instruction="x", page_context="y"))
        assert "RESOURCE_EXHAUSTED" not in str(raised.value)  # never the raw provider text
    assert fake.calls == 1
    summary = session.summary()
    assert summary["ai_enrichment_status"] == "unavailable"
    assert summary["deterministic_status"] == "completed"
    assert summary["error_kind"] == "quota"
    assert summary["notice"]["detail"] == "AI usage limit reached."
    assert "RESOURCE_EXHAUSTED" in summary["error_detail"]  # kept for Processing Details


def test_short_rate_limit_retries_once_then_succeeds():
    async def limited_then_ok(call, *_):
        if call == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED rate limit, retryDelay: '0.01s'")
        return {"values": [], "warnings": []}

    fake = FakeProvider(limited_then_ok)
    session = AIEnrichmentSession(provider=fake, timeout_seconds=5)
    assert _run(session.extract(instruction="x", page_context="y")) == {"values": [], "warnings": []}
    assert fake.calls == 2 and session.summary()["ai_enrichment_status"] == "completed"


def test_provider_5xx_retries_once_then_stops_for_the_run():
    async def unavailable(*_):
        raise RuntimeError("503 UNAVAILABLE high demand")

    fake = FakeProvider(unavailable)
    session = AIEnrichmentSession(provider=fake, timeout_seconds=5)
    with patch("app.services.ai_enrichment.asyncio.sleep", return_value=None):
        for _ in range(3):
            with pytest.raises(AIProviderError):
                _run(session.extract(instruction="x", page_context="y"))
    assert fake.calls == 2  # the first call and its single retry — nothing after
    assert session.summary()["error_kind"] == "provider_error"


def test_timeout_is_enforced_and_reported():
    async def slow(*_):
        await asyncio.sleep(5)

    session = AIEnrichmentSession(provider=FakeProvider(slow), timeout_seconds=0.05)
    started = time.perf_counter()
    with pytest.raises(AIProviderError):
        _run(session.extract(instruction="x", page_context="y"))
    assert time.perf_counter() - started < 2
    assert session.summary()["error_kind"] == "timeout"


def test_missing_key_means_no_provider_and_a_skipped_status():
    settings = runner_settings.model_copy(
        update={"ai_fallback_enabled": True, "ai_provider": "gemini", "gemini_api_key": None, "convera_enabled": False}
    )
    session = start_session(create_ai_provider(settings), settings)
    assert not session.available
    # Not configured: the same benign empty answer as the disabled provider.
    assert _run(session.extract(instruction="x", page_context="y"))["values"] == []
    assert session.summary()["ai_enrichment_status"] == "skipped"
    assert session.summary()["notice"] is None


# --- the real extraction job ----------------------------------------------------------------


def _statement_pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    lines = [
        "STATEMENT OF ACCOUNT",
        f"Account Number: ACCT-{uuid4().hex[:8].upper()}",
        "Statement Date: 03/14/2026",
        "Payment Terms: Net 30",
        "Customer Name: Cascade Water Authority",
        "Amount Due: $1,200.00",
    ]
    for i, text in enumerate(lines):
        page.insert_text((72, 72 + 18 * i), text, fontsize=10)
    return pdf.tobytes()


def _prepared_document() -> tuple[str, list[str]]:
    upload = client.post(
        "/api/documents/upload",
        files={"file": (f"ai-optional-{uuid4()}.pdf", _statement_pdf(), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]
    assert client.post(f"/api/documents/{document_id}/extract-pages", json={"run_ocr": False}).status_code == 200
    with patch("app.api.universal_extraction.create_ai_provider", return_value=DisabledAIProvider()):
        discover = client.post(f"/api/documents/{document_id}/discover-schema")
    assert discover.status_code == 200, discover.text
    target_ids = [t["id"] for t in discover.json()["targets"]]
    assert target_ids
    return document_id, target_ids


def _run_job(document_id: str, target_ids: list[str], provider, *, force_ai: bool = False, timeout: float | None = None) -> dict:
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.extraction_job_runner.create_ai_provider", return_value=provider))
        if force_ai:
            # Exercise the AI path itself: one field ("Payment Terms") is left
            # unresolved deterministically and the result is judged
            # insufficient, so the provider is actually consulted while every
            # other deterministic value remains.
            from app.services import target_extraction_service as tes

            original = tes._resolve_scalar_target

            def resolve(target, *args, **kwargs):
                resolved, retrieval, escalate = original(target, *args, **kwargs)
                if "payment terms" in (target.label or "").lower():
                    return None, retrieval, True
                return resolved, retrieval, escalate

            stack.enter_context(patch.object(tes, "_resolve_scalar_target", side_effect=resolve))
            stack.enter_context(
                patch.object(tes, "assess_deterministic_sufficiency", return_value=(False, "forced for test"))
            )
        if timeout is not None:
            stack.enter_context(patch.object(runner_settings, "ai_provider_attempt_timeout_seconds", timeout))
        start = client.post(
            f"/api/documents/{document_id}/jobs/extract",
            json={"target_ids": target_ids, "use_ai_fallback": True},
        )
        assert start.status_code == 202, start.text
        job_id = start.json()["id"]
        job = None
        for _ in range(200):
            job = client.get(f"/v1/jobs/{job_id}").json()
            if job["status"] in ("complete", "failed"):
                break
            time.sleep(0.05)
    assert job is not None
    return job


def _workbook(document_id: str) -> dict:
    response = client.get(f"/api/documents/{document_id}/staging-workbook")
    assert response.status_code == 200, response.text
    return response.json()


def test_quota_429_with_good_deterministic_extraction_completes_without_calling_ai():
    document_id, target_ids = _prepared_document()
    fake = FakeProvider(_quota)
    job = _run_job(document_id, target_ids, fake)
    assert job["status"] == "complete", job
    ai = job["result"]["ai_enrichment"]
    assert ai["deterministic_status"] == "completed"
    assert ai["ai_enrichment_status"] == "not_needed"
    assert fake.calls == 0  # deterministic result was sufficient: no AI at all
    assert _workbook(document_id)["outcome"]["status"] in ("populated", "needs_review")


def test_quota_429_on_forced_ai_path_keeps_results_with_one_call_and_a_quiet_qa_notice():
    document_id, target_ids = _prepared_document()
    baseline = _run_job(document_id, target_ids, DisabledAIProvider(), force_ai=True)
    baseline_workbook = _workbook(document_id)

    document_id, target_ids = _prepared_document()
    fake = FakeProvider(_quota)
    job = _run_job(document_id, target_ids, fake, force_ai=True)
    assert job["status"] == "complete", job
    ai = job["result"]["ai_enrichment"]
    assert ai["ai_enrichment_status"] == "unavailable"
    assert ai["notice"]["title"] == "AI enhancement skipped. Deterministic extraction completed successfully."
    assert fake.calls == 1  # breaker: no repeated provider calls across targets/batches
    # No raw provider exception in the results' warnings.
    assert not any("RESOURCE_EXHAUSTED" in w or "429" in w for w in job["result"]["warnings"])
    # Deterministic values survive; AI's failure flags nothing for review.
    assert len(job["result"]["scalars"]) == len(baseline["result"]["scalars"]) > 0

    workbook = _workbook(document_id)
    assert workbook["processing_metadata"]["ai_enrichment_status"] == "unavailable"
    assert workbook["qa_summary"]["needs_review"] == baseline_workbook["qa_summary"]["needs_review"]
    qa = next(d for d in workbook["datasets"] if d["role"] == "qa")
    notice = [r for r in qa["records"] if r["record_id"] == "qa:ai_enrichment"]
    assert len(notice) == 1
    cells = {k.rsplit(".", 1)[-1]: c["value"] for k, c in notice[0]["cells"].items()}
    assert cells["result"] == "INFO"
    assert cells["details"].startswith("AI enrichment unavailable — deterministic results shown.")


def test_ai_timeout_keeps_the_deterministic_result():
    document_id, target_ids = _prepared_document()

    async def hang(*_):
        await asyncio.sleep(30)

    job = _run_job(document_id, target_ids, FakeProvider(hang), force_ai=True, timeout=0.2)
    assert job["status"] == "complete", job
    ai = job["result"]["ai_enrichment"]
    assert (ai["ai_enrichment_status"], ai["error_kind"]) == ("unavailable", "timeout")
    assert job["result"]["scalars"]


def test_no_ai_key_keeps_the_deterministic_result():
    document_id, target_ids = _prepared_document()
    job = _run_job(document_id, target_ids, DisabledAIProvider(), force_ai=True)
    assert job["status"] == "complete", job
    assert job["result"]["ai_enrichment"]["ai_enrichment_status"] == "skipped"
    assert job["result"]["scalars"]
    assert not any("AI fallback" in w for w in job["result"]["warnings"])


def test_ai_value_without_source_support_is_never_staged():
    document_id, target_ids = _prepared_document()

    async def invented(_call, instruction, _context):
        labels = [part.strip(' ".') for part in instruction.split(":", 1)[-1].split(";")]
        return {
            "answer": None,
            "values": [
                {"label": label, "value": "ZZ-INVENTED-9999", "page_number": 1, "source_text": "ZZ-INVENTED-9999", "confidence": 0.99}
                for label in labels if label
            ],
            "warnings": [],
        }

    job = _run_job(document_id, target_ids, FakeProvider(invented), force_ai=True)
    assert job["status"] == "complete", job
    assert not any("ZZ-INVENTED-9999" in str(s.get("value")) for s in job["result"]["scalars"])
    workbook = _workbook(document_id)
    for dataset in workbook["datasets"]:
        for record in dataset["records"]:
            for cell in record["cells"].values():
                assert "ZZ-INVENTED-9999" not in str(cell["value"])


def test_instruction_extraction_survives_ai_quota_exhaustion():
    document_id, _ = _prepared_document()
    fake = FakeProvider(_quota)
    session = AIEnrichmentSession(provider=fake, timeout_seconds=5)
    with patch("app.api.universal_extraction.start_session", return_value=session):
        response = client.post(
            f"/api/documents/{document_id}/extract",
            json={"instruction": "What is the customer name on this statement of account?", "use_ai_fallback": True},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "AI enhancement skipped — deterministic results shown." in body["warnings"]
    assert not any("RESOURCE_EXHAUSTED" in w for w in body["warnings"])
    assert fake.calls == 1
