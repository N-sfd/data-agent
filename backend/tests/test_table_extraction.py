from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_rate_card_pdf() -> bytes:
    """
    Builds a real ruled table (pdfplumber's default table-detection
    strategy needs actual grid lines, not just aligned text) with a
    Role/Rate header and two data rows.
    """

    pdf = fitz.open()
    page = pdf.new_page()

    left, right = 72, 320
    row_tops = [100, 124, 148, 172]
    mid = 220

    for y in row_tops:
        page.draw_line((left, y), (right, y))

    for x in (left, mid, right):
        page.draw_line((x, row_tops[0]), (x, row_tops[-1]))

    rows = [
        ("Role", "Rate"),
        ("Project Manager", "$175/hr"),
        ("Developer", "$145/hr"),
    ]

    for row_index, (col1, col2) in enumerate(rows):
        y = row_tops[row_index] + 16
        page.insert_text((left + 6, y), col1, fontsize=9)
        page.insert_text((mid + 6, y), col2, fontsize=9)

    content = pdf.tobytes()
    pdf.close()

    return content


def upload_and_extract(content: bytes, filename: str) -> str:
    response = client.post(
        "/api/documents/upload",
        files={"file": (filename, content, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]

    extraction = client.post(
        f"/api/documents/{document_id}/extract-pages",
        json={
            "run_ocr": False,
            "page_start": None,
            "page_end": None,
            "force_reprocess": False,
        },
    )

    assert extraction.status_code == 200, extraction.text

    return document_id


def test_extract_tables_types_rate_card() -> None:
    document_id = upload_and_extract(
        create_rate_card_pdf(),
        f"rate-card-{uuid4()}.pdf",
    )

    response = client.post(
        f"/api/documents/{document_id}/extract-tables"
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["tables"]) == 1
    table = body["tables"][0]

    assert table["table_type"] == "rate_card"
    assert table["page_number"] == 1

    rows_by_role = {
        row["role"]: row for row in table["rate_card_rows"]
    }

    assert rows_by_role["Project Manager"]["rate"] == 175.0
    assert rows_by_role["Project Manager"]["unit"] == "hour"
    assert rows_by_role["Project Manager"]["currency"] == "USD"

    assert rows_by_role["Developer"]["rate"] == 145.0
    assert rows_by_role["Developer"]["unit"] == "hour"


def test_extract_tables_on_document_without_tables() -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), f"No tables here {uuid4()}")
    content = pdf.tobytes()
    pdf.close()

    document_id = upload_and_extract(
        content, f"no-tables-{uuid4()}.pdf"
    )

    response = client.post(
        f"/api/documents/{document_id}/extract-tables"
    )

    assert response.status_code == 200
    assert response.json()["tables"] == []


def test_extract_tables_unknown_document_returns_404() -> None:
    response = client.post(
        "/api/documents/not-a-real-id/extract-tables"
    )

    assert response.status_code == 404
