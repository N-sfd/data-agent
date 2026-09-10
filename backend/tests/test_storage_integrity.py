"""Storage integrity + source_status reporting."""

from pathlib import Path
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.main import app
from app.models.document import Document

client = TestClient(app)


def _pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), f"Integrity probe {uuid4()}")
    content = pdf.tobytes()
    pdf.close()
    return content


def test_source_status_available_after_upload() -> None:
    upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                f"source-ok-{uuid4()}.pdf",
                _pdf(),
                "application/pdf",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    detail = client.get(f"/api/documents/{document_id}")
    assert detail.json()["source_status"] == "available"

    listed = client.get("/api/documents", params={"limit": 25}).json()
    match = next(d for d in listed if d["document_id"] == document_id)
    assert match["source_status"] == "available"


def test_storage_integrity_reports_missing_after_local_wipe() -> None:
    upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                f"source-gone-{uuid4()}.pdf",
                _pdf(),
                "application/pdf",
            )
        },
    )
    document_id = upload.json()["document_id"]
    settings = get_settings()

    database = SessionLocal()
    try:
        document = database.get(Document, document_id)
        assert document is not None
        path = Path(settings.upload_path) / document.stored_filename
        assert path.exists()
        path.unlink()
    finally:
        database.close()

    detail = client.get(f"/api/documents/{document_id}")
    assert detail.json()["source_status"] == "missing"

    integrity = client.get("/api/system/storage-integrity")
    assert integrity.status_code == 200
    body = integrity.json()
    assert body["missing"] >= 1
    assert any(
        row["document_id"] == document_id for row in body["missing_sample"]
    )
