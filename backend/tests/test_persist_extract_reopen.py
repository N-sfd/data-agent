"""P0: Persist → reopen → Explorer without re-extract.

Fresh PDF → upload → pages → discover → extract job → durable rows →
GET extract-results (no re-extract) → wipe local PDF + restore →
source verification still works from persisted evidence.
"""

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
    page.insert_text((72, 112), "Effective Date: 2026-01-15", fontsize=10)
    content = pdf.tobytes()
    pdf.close()
    return content


def _upload_process_discover(marker: str) -> str:
    upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                f"persist-{uuid4()}.pdf",
                _pdf(marker),
                "application/pdf",
            )
        },
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

    with patch(
        "app.api.universal_extraction.create_ai_provider",
        return_value=DisabledAIProvider(),
    ):
        discover = client.post(
            f"/api/documents/{document_id}/discover-schema"
        )
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


def test_extract_persists_and_reopens_without_reextract() -> None:
    marker = f"W912DR-{uuid4().hex[:8].upper()}"
    document_id = _upload_process_discover(marker)

    targets = client.get(f"/api/documents/{document_id}/targets").json()[
        "targets"
    ]
    assert targets
    for target in targets:
        assert target.get("selectable", True) is True
        assert target.get("is_internal", False) is False

    field_ids = [
        t["id"]
        for t in targets
        if t.get("target_type") != "table" and t.get("source_examples")
    ]
    assert field_ids
    job = _run_job(document_id, field_ids[:10])
    assert job["result"]["scalars"] or job["result"]["unresolved_targets"]
    if job["result"]["scalars"]:
        first = job["result"]["scalars"][0]
        assert "retrieval" in first
        assert first["retrieval"]["target_key"]
        assert "selected_pages" in first["retrieval"]
        assert "confidence_detail" in first
        assert "signals" in first["confidence_detail"]
        assert "exact_label_match" in first["confidence_detail"]["signals"]
        assert "validation" in first
        assert first["validation"]["status"] in {"passed", "failed", "skipped"}
        assert isinstance(first["validation"]["checks"], list)

    # Durable rows in PostgreSQL / SQLite
    database = SessionLocal()
    try:
        rows = list(
            database.scalars(
                select(DocumentMetadataField).where(
                    DocumentMetadataField.document_id == document_id,
                    DocumentMetadataField.extraction_source == "target",
                )
            )
        )
        assert rows, "expected persisted target metadata fields"
        sample = rows[0]
        assert sample.evidence_json
        assert sample.extraction_method
        assert sample.confidence is not None
        assert sample.review_status == "pending"
    finally:
        database.close()

    # Reopen path: GET extract-results must not require a new job
    persisted = client.get(f"/api/documents/{document_id}/extract-results")
    assert persisted.status_code == 200, persisted.text
    body = persisted.json()
    assert body["document_id"] == document_id
    assert body["scalars"]

    scalar = next(
        (s for s in body["scalars"] if marker in str(s.get("value"))),
        body["scalars"][0],
    )
    assert "evidence" in scalar
    assert scalar["evidence"]["page_number"] >= 1
    assert scalar["extraction_method"]
    assert "confidence" in scalar
    # Intelligence objects survive reopen (may be reconstructed for older rows).
    assert scalar.get("confidence_detail") is not None
    assert scalar.get("validation") is not None
    if scalar.get("retrieval"):
        assert "selected_pages" in scalar["retrieval"]
        assert "candidate_pages" in scalar["retrieval"]

    # Source verification from persisted evidence
    render = client.get(
        f"/api/documents/{document_id}/pages/{scalar['page']}/render",
        params={"highlight": str(scalar["value"])[:80]},
    )
    assert render.status_code == 200, render.text

    # Simulated Render restart: wipe local, restore remote, reopen still works
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
        assert again.json()["scalars"]
        restored = client.get(
            f"/api/documents/{document_id}/pages/{scalar['page']}/render",
            params={"highlight": str(scalar["value"])[:80]},
        )
        assert restored.status_code == 200, restored.text
        assert (
            client.get(f"/api/documents/{document_id}").json()["source_status"]
            == "available"
        )
