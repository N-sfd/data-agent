from typing import Any
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_provider import AIProvider
from app.services.contract_field_schema import FieldSpec


client = TestClient(app)


class DashboardStubAIProvider(AIProvider):
    async def extract(
        self, *, instruction: str, page_context: str
    ) -> dict[str, Any]:
        return {"answer": None, "values": [], "warnings": []}

    async def classify(self, *, page_context: str) -> dict[str, Any]:
        return {
            "document_type": "Master Services Agreement",
            "industry": "Technology",
            "contract_side": "buy_side",
            "language": "English",
            "confidence": 0.95,
        }

    async def extract_fields(
        self, *, page_context: str, field_specs: list[FieldSpec]
    ) -> dict[str, Any]:
        return {"fields": []}

    async def extract_clauses(
        self, *, page_context: str
    ) -> dict[str, Any]:
        return {"clauses": []}

    async def extract_signatures(
        self, *, page_context: str
    ) -> dict[str, Any]:
        return {"signatures": []}


def create_pdf(lines: list[str]) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()

    y = 72
    for line in lines:
        page.insert_text((72, y), line)
        y += 20

    content = pdf.tobytes()
    pdf.close()

    return content


def upload(lines: list[str], filename: str) -> str:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (filename, create_pdf(lines), "application/pdf")
        },
    )

    assert response.status_code == 201, response.text

    return response.json()["document_id"]


def extract_pages(document_id: str) -> None:
    response = client.post(
        f"/api/documents/{document_id}/extract-pages",
        json={
            "run_ocr": False,
            "page_start": None,
            "page_end": None,
            "force_reprocess": False,
        },
    )

    assert response.status_code == 200, response.text


def analyze(document_id: str) -> dict:
    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=DashboardStubAIProvider(),
    ):
        response = client.post(
            f"/api/documents/{document_id}/analyze-contract"
        )

    assert response.status_code == 200, response.text

    return response.json()


def find_document(document_id: str) -> dict:
    response = client.get("/api/documents", params={"limit": 100})
    assert response.status_code == 200

    for document in response.json():
        if document["document_id"] == document_id:
            return document

    raise AssertionError(
        f"document {document_id} not found in list response"
    )


def test_document_awaiting_extraction_review_required() -> None:
    document_id = upload(
        [f"Not yet analyzed {uuid4()}"], f"pending-{uuid4()}.pdf"
    )
    extract_pages(document_id)

    document = find_document(document_id)
    assert document["status"] == "review_required"
    assert document["document_type"] is None


def test_document_becomes_completed_after_full_review() -> None:
    document_id = upload(
        [
            "Contract Title: Master Services Agreement",
            f"Governing Law: State of Delaware {uuid4()}",
        ],
        f"full-review-{uuid4()}.pdf",
    )
    extract_pages(document_id)
    analyzed = analyze(document_id)

    # Still has pending fields right after analysis.
    document = find_document(document_id)
    assert document["status"] == "review_required"
    assert document["document_type"] == (
        "Master Services Agreement"
    )

    assert len(analyzed["metadata_fields"]) > 0

    accept_response = client.post(
        f"/api/documents/{document_id}/metadata-fields/accept-all",
        json={"changed_by": "Test Reviewer"},
    )
    assert accept_response.status_code == 200

    document = find_document(document_id)
    assert document["status"] == "completed"
    assert document["confidence"] is not None


def test_dashboard_stats_reflect_known_document() -> None:
    document_id = upload(
        [
            "Contract Title: Master Services Agreement",
            f"Payment Terms: Net 30 {uuid4()}",
        ],
        f"stats-{uuid4()}.pdf",
    )
    extract_pages(document_id)
    analyzed = analyze(document_id)
    assert len(analyzed["metadata_fields"]) > 0

    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    stats = response.json()

    assert stats["total_documents"] >= 1
    assert stats["fields_extracted"] >= len(
        analyzed["metadata_fields"]
    )
    assert 0 <= stats["extraction_accuracy"] <= 1
    assert 0 <= stats["human_review_rate"] <= 100
    assert (
        stats["completed"]
        + stats["review_required"]
        + stats["processing"]
        == stats["total_documents"]
    )
