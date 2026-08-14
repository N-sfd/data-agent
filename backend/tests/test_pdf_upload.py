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
