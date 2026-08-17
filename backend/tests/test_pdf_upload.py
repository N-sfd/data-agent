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
                "financial-report.txt",
                b"not a pdf",
                "text/plain",
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
