from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_test_pdf(marker: str) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), f"Contract Title: {marker}")
    page.insert_text((72, 100), "Payment Terms: Net 30")

    content = pdf.tobytes()
    pdf.close()

    return content


def create_test_docx() -> bytes:
    from io import BytesIO

    from docx import Document as DocxDocument

    document = DocxDocument()
    document.add_paragraph(f"Rendering not supported {uuid4()}")

    buffer = BytesIO()
    document.save(buffer)

    return buffer.getvalue()


def upload_pdf(marker: str) -> str:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                f"{marker}.pdf",
                create_test_pdf(marker),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201, response.text

    return response.json()["document_id"]


def test_render_page_with_highlight_found() -> None:
    marker = str(uuid4())
    document_id = upload_pdf(marker)

    response = client.get(
        f"/api/documents/{document_id}/pages/1/render",
        params={"highlight": "Net 30"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["page_number"] == 1
    assert body["image_data_url"].startswith(
        "data:image/png;base64,"
    )
    assert body["page_width"] > 0
    assert body["page_height"] > 0

    assert body["highlight"] is not None
    assert body["highlight"]["x1"] > body["highlight"]["x0"]
    assert body["highlight"]["y1"] > body["highlight"]["y0"]


def test_render_page_without_matching_highlight() -> None:
    marker = str(uuid4())
    document_id = upload_pdf(marker)

    response = client.get(
        f"/api/documents/{document_id}/pages/1/render",
        params={"highlight": "Text That Does Not Appear Anywhere"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["highlight"] is None


def test_render_page_without_highlight_param() -> None:
    marker = str(uuid4())
    document_id = upload_pdf(marker)

    response = client.get(
        f"/api/documents/{document_id}/pages/1/render"
    )

    assert response.status_code == 200
    assert response.json()["highlight"] is None


def test_render_nonexistent_page() -> None:
    marker = str(uuid4())
    document_id = upload_pdf(marker)

    response = client.get(
        f"/api/documents/{document_id}/pages/99/render"
    )

    assert response.status_code == 404


def test_render_rejects_non_pdf_document() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "notes.docx",
                create_test_docx(),
                (
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
            )
        },
    )

    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]

    response = client.get(
        f"/api/documents/{document_id}/pages/1/render"
    )

    assert response.status_code == 422
