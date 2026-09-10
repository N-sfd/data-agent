"""Explainability must survive extract → reopen → simulated restart."""

from __future__ import annotations

import time
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.services.ai_provider import DisabledAIProvider
from sqlalchemy import select

client = TestClient(app)


def _pdf(marker: str) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), f"Contract Number: {marker}", fontsize=10)
    page.insert_text((72, 92), "Payment Terms: Net 30", fontsize=10)
    content = pdf.tobytes()
    pdf.close()
    return content


def _upload_process_discover(marker: str) -> str:
    upload = client.post(
        "/api/documents/upload",
        files={"file": (f"explain-{uuid4()}.pdf", _pdf(marker), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]
    assert (
        client.post(
            f"/api/documents/{document_id}/extract-pages",
            json={
                "run_ocr": False,
                "page_start": None,
                "page_end": None,
                "force_reprocess": False,
            },
        ).status_code
        == 200
    )
    with patch(
        "app.api.universal_extraction.create_ai_provider",
        return_value=DisabledAIProvider(),
    ):
        discover = client.post(f"/api/documents/{document_id}/discover-schema")
    assert discover.status_code == 200, discover.text
    return document_id


def _run_job(document_id: str, target_ids: list[str]) -> dict:
    start = client.post(
        f"/api/documents/{document_id}/jobs/extract",
        json={"target_ids": target_ids, "use_ai_fallback": False},
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


def test_explainability_persists_across_reopen_and_restart() -> None:
    marker = f"W912DR-{uuid4().hex[:8].upper()}"
    document_id = _upload_process_discover(marker)
    targets = client.get(f"/api/documents/{document_id}/targets").json()["targets"]
    field_ids = [
        target["id"]
        for target in targets
        if target.get("target_type") != "table" and target.get("source_examples")
    ]
    assert field_ids
    job = _run_job(document_id, field_ids[:8])
    assert job["result"]["scalars"]

    live = job["result"]["scalars"][0]
    assert live.get("retrieval")
    assert live.get("confidence_detail")
    assert live.get("validation")
    live_snapshot = {
        "retrieval": live["retrieval"],
        "confidence": live["confidence_detail"],
        "validation": live["validation"],
        "value": live["value"],
        "extraction_method": live["extraction_method"],
        "page": live["page"],
    }

    # Durable evidence_json must carry the intelligence objects.
    database = SessionLocal()
    try:
        row = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.extraction_source == "target",
                DocumentMetadataField.field_key == live["normalized_key"],
            )
        )
        assert row is not None
        evidence = row.evidence_json or {}
        assert "retrieval" in evidence
        assert "confidence_detail" in evidence
        assert "validation" in evidence
    finally:
        database.close()

    reopened = client.get(f"/api/documents/{document_id}/extract-results")
    assert reopened.status_code == 200
    reopened_scalar = next(
        item
        for item in reopened.json()["scalars"]
        if item["normalized_key"] == live["normalized_key"]
    )
    assert reopened_scalar["retrieval"]["selected_pages"] == live_snapshot["retrieval"][
        "selected_pages"
    ]
    assert reopened_scalar["retrieval"]["deterministic_status"] == live_snapshot[
        "retrieval"
    ]["deterministic_status"]
    assert reopened_scalar["confidence_detail"]["score"] == live_snapshot["confidence"][
        "score"
    ]
    assert reopened_scalar["confidence_detail"]["signals"] == live_snapshot["confidence"][
        "signals"
    ]
    assert reopened_scalar["validation"]["status"] == live_snapshot["validation"]["status"]
    assert reopened_scalar["validation"]["checks"] == live_snapshot["validation"]["checks"]

    # Simulated Render restart: wipe local PDF, restore remote, reopen same trace.
    settings = get_settings()
    database = SessionLocal()
    try:
        document = database.get(Document, document_id)
        assert document is not None
        path = settings.upload_path / document.stored_filename
        original = path.read_bytes()
        path.unlink()
    finally:
        database.close()

    with patch(
        "app.services.document_storage.download_object",
        return_value=original,
    ), patch(
        "app.services.document_storage.object_exists",
        return_value=True,
    ):
        again = client.get(f"/api/documents/{document_id}/extract-results")
        assert again.status_code == 200
        again_scalar = next(
            item
            for item in again.json()["scalars"]
            if item["normalized_key"] == live["normalized_key"]
        )
        assert again_scalar["confidence_detail"]["signals"] == live_snapshot["confidence"][
            "signals"
        ]
        assert again_scalar["validation"]["checks"] == live_snapshot["validation"]["checks"]
        assert again_scalar["retrieval"]["candidate_pages"] == live_snapshot["retrieval"][
            "candidate_pages"
        ]
