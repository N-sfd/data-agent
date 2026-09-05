from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_pdf(lines: list[str]) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()

    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=9)
        y += 14

    content = pdf.tobytes()
    pdf.close()

    return content


def upload_document(filename: str) -> str:
    upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                filename,
                create_pdf(["Contract Number: W912DR-26-C-0042"]),
                "application/pdf",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    return upload.json()["document_id"]


def test_create_and_list_target_correction() -> None:
    document_id = upload_document(f"correction-{uuid4()}.pdf")

    create_response = client.post(
        f"/api/documents/{document_id}/targets/contract_number/corrections",
        json={
            "original_value": "W912DR-26-C-0042",
            "corrected_value": "W912DR-26-C-0043",
            "evidence": {
                "page_number": 1,
                "source_text": "Contract Number: W912DR-26-C-0042",
                "source_reference": "Page 1",
            },
            "changed_by": "reviewer@example.com",
        },
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    assert body["original_value"] == "W912DR-26-C-0042"
    assert body["corrected_value"] == "W912DR-26-C-0043"
    assert body["evidence_snapshot"]["page_number"] == 1

    list_response = client.get(f"/api/documents/{document_id}/corrections")
    assert list_response.status_code == 200, list_response.text
    corrections = list_response.json()
    assert len(corrections) == 1
    assert corrections[0]["normalized_key"] == "contract_number"
    assert corrections[0]["corrected_value"] == "W912DR-26-C-0043"


def test_second_edit_replaces_latest_value_but_keeps_history() -> None:
    document_id = upload_document(f"correction-history-{uuid4()}.pdf")

    client.post(
        f"/api/documents/{document_id}/targets/contract_number/corrections",
        json={
            "original_value": "W912DR-26-C-0042",
            "corrected_value": "First Correction",
        },
    )
    client.post(
        f"/api/documents/{document_id}/targets/contract_number/corrections",
        json={
            "original_value": "First Correction",
            "corrected_value": "Second Correction",
        },
    )

    list_response = client.get(f"/api/documents/{document_id}/corrections")
    corrections = list_response.json()
    assert len(corrections) == 1
    assert corrections[0]["corrected_value"] == "Second Correction"


def test_correction_requires_existing_document() -> None:
    response = client.post(
        f"/api/documents/{uuid4()}/targets/contract_number/corrections",
        json={"original_value": "a", "corrected_value": "b"},
    )
    assert response.status_code == 404
