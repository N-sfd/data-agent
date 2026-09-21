from io import BytesIO
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_test_pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    # Unique text avoids SHA-256 duplicate collisions across re-runs
    # until a dedicated test database/cleanup fixture exists.
    page.insert_text(
        (72, 72),
        f"FY2025 Financial Report {uuid4()}",
    )

    content = pdf.tobytes()
    pdf.close()

    return content


def test_upload_valid_pdf() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "financial-report.pdf",
                create_test_pdf(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["status"] == "ready"
    assert body["content_type"] == "application/pdf"
    assert body["page_count"] == 1
    assert body["encrypted"] is False
    assert len(body["checksum_sha256"]) == 64


def test_reject_non_pdf_extension() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "financial-report.exe",
                b"MZ not a document",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400


def test_reject_fake_pdf() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "fake.pdf",
                b"This is not actually a PDF.",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert "PDF signature" in response.json()["detail"]


def test_duplicate_upload_is_surfaced_not_silently_reused() -> None:
    content = create_test_pdf()

    first = client.post(
        "/api/documents/upload",
        files={
            "file": ("original.pdf", content, "application/pdf")
        },
    )

    assert first.status_code == 201
    original = first.json()

    second = client.post(
        "/api/documents/upload",
        files={
            "file": ("original-copy.pdf", content, "application/pdf")
        },
    )

    assert second.status_code == 200

    body = second.json()

    assert body["duplicate"] is True
    assert body["status"] == "duplicate_pending"
    assert body["document_id"] != original["document_id"]
    assert (
        body["existing_document"]["document_id"]
        == original["document_id"]
    )


def test_resolve_duplicate_use_existing() -> None:
    content = create_test_pdf()

    first = client.post(
        "/api/documents/upload",
        files={
            "file": ("original.pdf", content, "application/pdf")
        },
    )

    original = first.json()

    second = client.post(
        "/api/documents/upload",
        files={
            "file": ("original-copy.pdf", content, "application/pdf")
        },
    )

    staged_document_id = second.json()["document_id"]

    resolved = client.post(
        f"/api/documents/{staged_document_id}/resolve-duplicate",
        json={"action": "use_existing"},
    )

    assert resolved.status_code == 200

    body = resolved.json()

    assert body["document_id"] == original["document_id"]
    assert body.get("duplicate", False) is False


def test_resolve_duplicate_upload_anyway() -> None:
    content = create_test_pdf()

    first = client.post(
        "/api/documents/upload",
        files={
            "file": ("original.pdf", content, "application/pdf")
        },
    )

    original = first.json()

    second = client.post(
        "/api/documents/upload",
        files={
            "file": ("original-copy.pdf", content, "application/pdf")
        },
    )

    staged_document_id = second.json()["document_id"]

    resolved = client.post(
        f"/api/documents/{staged_document_id}/resolve-duplicate",
        json={
            "action": "upload_anyway",
            "original_filename": "original-copy.pdf",
        },
    )

    assert resolved.status_code == 200

    body = resolved.json()

    assert body["status"] == "ready"
    assert body["document_id"] == staged_document_id
    assert body["document_id"] != original["document_id"]
    assert body["checksum_sha256"] == original["checksum_sha256"]


def test_allow_duplicate_skips_duplicate_gate() -> None:
    content = create_test_pdf()

    first = client.post(
        "/api/documents/upload",
        files={"file": ("a.pdf", content, "application/pdf")},
    )
    assert first.status_code == 201
    original_id = first.json()["document_id"]

    second = client.post(
        "/api/documents/upload?allow_duplicate=true",
        files={"file": ("a-copy.pdf", content, "application/pdf")},
    )
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["duplicate"] is False
    assert body["status"] == "ready"
    assert body["document_id"] != original_id


def test_use_existing_without_staged_file() -> None:
    content = create_test_pdf()

    first = client.post(
        "/api/documents/upload",
        files={"file": ("keep.pdf", content, "application/pdf")},
    )
    original_id = first.json()["document_id"]

    # Fake a staged id that has no file on disk.
    from uuid import uuid4

    fake_staged = str(uuid4())
    resolved = client.post(
        f"/api/documents/{fake_staged}/resolve-duplicate",
        json={
            "action": "use_existing",
            "existing_document_id": original_id,
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["document_id"] == original_id


def test_upload_anyway_without_staged_returns_expired() -> None:
    from uuid import uuid4

    fake_staged = str(uuid4())
    resolved = client.post(
        f"/api/documents/{fake_staged}/resolve-duplicate",
        json={"action": "upload_anyway"},
    )
    assert resolved.status_code == 409
    assert "STAGED_UPLOAD_EXPIRED" in resolved.json()["detail"]
