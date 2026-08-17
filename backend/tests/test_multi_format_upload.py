from io import BytesIO
from uuid import uuid4

from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app


client = TestClient(app)


def create_test_docx() -> bytes:
    # Unique text avoids SHA-256 duplicate collisions across re-runs
    # until a dedicated test database/cleanup fixture exists.
    document = DocxDocument()
    document.add_paragraph("Master Services Agreement")
    document.add_paragraph(
        f"This agreement is between Acme and Globex. {uuid4()}"
    )

    buffer = BytesIO()
    document.save(buffer)

    return buffer.getvalue()


def create_test_png() -> bytes:
    # Unique text avoids SHA-256 duplicate collisions across re-runs
    # until a dedicated test database/cleanup fixture exists.
    image = Image.new("RGB", (300, 80), color="white")
    ImageDraw.Draw(image).text((10, 30), str(uuid4()), fill="black")

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def test_upload_docx_extracts_text_immediately() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "msa.docx",
                create_test_docx(),
                (
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
            )
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["status"] == "ready"
    assert body["page_count"] == 1

    document_id = body["document_id"]

    pages = client.get(
        f"/api/documents/{document_id}/pages"
    )

    assert pages.status_code == 200
    stored_pages = pages.json()

    assert len(stored_pages) == 1
    assert "Master Services Agreement" in stored_pages[0]["final_text"]


def test_reject_docx_that_is_not_really_ooxml() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "fake.docx",
                b"not actually a docx",
                (
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
            )
        },
    )

    assert response.status_code == 400


def test_upload_png_and_extract_pages() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": ("scan.png", create_test_png(), "image/png")
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["status"] == "ready"
    assert body["content_type"] == "image/png"
    assert body["page_count"] == 1

    document_id = body["document_id"]

    extraction = client.post(
        f"/api/documents/{document_id}/extract-pages",
        json={
            "run_ocr": True,
            "page_start": None,
            "page_end": None,
            "force_reprocess": False,
        },
    )

    assert extraction.status_code == 200
    assert extraction.json()["pages_processed"] == 1


def test_reject_unsupported_extension() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "notes.txt",
                b"plain text",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
