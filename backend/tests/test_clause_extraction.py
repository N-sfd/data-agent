from typing import Any
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_provider import AIProvider
from app.services.contract_field_schema import FieldSpec


client = TestClient(app)

LIABILITY_TEXT = (
    "Neither party's aggregate liability shall exceed two times "
    "the annual fees paid under this Agreement."
)


class ClauseStubAIProvider(AIProvider):
    """Returns a single grounded clause for testing."""

    async def extract(
        self, *, instruction: str, page_context: str
    ) -> dict[str, Any]:
        return {"answer": None, "values": [], "warnings": []}

    async def classify(self, *, page_context: str) -> dict[str, Any]:
        return {
            "document_type": "Other",
            "industry": None,
            "contract_side": "unknown",
            "language": None,
            "confidence": 0.0,
        }

    async def extract_fields(
        self, *, page_context: str, field_specs: list[FieldSpec]
    ) -> dict[str, Any]:
        return {"fields": []}

    async def extract_signatures(
        self, *, page_context: str
    ) -> dict[str, Any]:
        return {"signatures": []}

    async def extract_clauses(
        self, *, page_context: str
    ) -> dict[str, Any]:
        return {
            "clauses": [
                {
                    "clause_type": "Liability",
                    "classification": "Mutual Liability Cap",
                    "extracted_text": LIABILITY_TEXT,
                    "value_summary": "2x Annual Fees",
                    "page_number": 1,
                    "confidence": 0.96,
                },
                # An ungrounded clause the validator must drop.
                {
                    "clause_type": "Termination",
                    "classification": "Fabricated",
                    "extracted_text": (
                        "This text does not appear anywhere "
                        "in the document."
                    ),
                    "value_summary": "",
                    "page_number": 1,
                    "confidence": 0.9,
                },
                # An unknown clause type must be dropped too.
                {
                    "clause_type": "Not A Real Clause Type",
                    "classification": "N/A",
                    "extracted_text": LIABILITY_TEXT,
                    "value_summary": "",
                    "page_number": 1,
                    "confidence": 0.9,
                },
            ]
        }


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


def upload_and_extract(lines: list[str], filename: str) -> str:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (filename, create_pdf(lines), "application/pdf")
        },
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


def test_extract_clauses_grounds_and_filters() -> None:
    document_id = upload_and_extract(
        [
            "LIMITATION OF LIABILITY",
            LIABILITY_TEXT,
        ],
        f"clauses-{uuid4()}.pdf",
    )

    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=ClauseStubAIProvider(),
    ):
        response = client.post(
            f"/api/documents/{document_id}/extract-clauses"
        )

    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["clauses"]) == 1

    clause = body["clauses"][0]
    assert clause["clause_type"] == "Liability"
    assert clause["classification"] == "Mutual Liability Cap"
    assert clause["value_summary"] == "2x Annual Fees"
    assert clause["extracted_text"] == LIABILITY_TEXT
    assert clause["evidence"]["page_number"] == 1

    assert len(body["warnings"]) == 1


def test_extract_clauses_requires_extracted_pages() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                f"unready-{uuid4()}.pdf",
                create_pdf(["No pages extracted yet."]),
                "application/pdf",
            )
        },
    )

    document_id = response.json()["document_id"]

    response = client.post(
        f"/api/documents/{document_id}/extract-clauses"
    )

    assert response.status_code == 409


def test_get_clauses_reads_back_persisted_state() -> None:
    document_id = upload_and_extract(
        [
            "LIMITATION OF LIABILITY",
            LIABILITY_TEXT,
        ],
        f"clauses-readback-{uuid4()}.pdf",
    )

    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=ClauseStubAIProvider(),
    ):
        client.post(f"/api/documents/{document_id}/extract-clauses")

    response = client.get(
        f"/api/documents/{document_id}/extract-clauses"
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body["clauses"]) == 1
    assert body["clauses"][0]["clause_type"] == "Liability"
