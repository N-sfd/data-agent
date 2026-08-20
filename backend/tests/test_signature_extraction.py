from typing import Any
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_provider import AIProvider
from app.services.contract_field_schema import FieldSpec


client = TestClient(app)

SIGNATURE_BLOCK = (
    "ABC Technologies Inc. By: Jane Smith, Vice President, Sales "
    "Date: December 18, 2025"
)


class SignatureStubAIProvider(AIProvider):
    """Returns a grounded signature and an ungrounded one for testing."""

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

    async def extract_clauses(
        self, *, page_context: str
    ) -> dict[str, Any]:
        return {"clauses": []}

    async def extract_signatures(
        self, *, page_context: str
    ) -> dict[str, Any]:
        return {
            "signatures": [
                {
                    "party_name": "ABC Technologies Inc.",
                    "signatory_name": "Jane Smith",
                    "signatory_title": "Vice President, Sales",
                    "signed": True,
                    "signature_date": "December 18, 2025",
                    "page_number": 1,
                    "source_text": SIGNATURE_BLOCK,
                    "confidence": 0.94,
                },
                # An ungrounded signature the validator must drop.
                {
                    "party_name": "Fabricated Corp",
                    "signatory_name": "Nobody",
                    "signatory_title": "CEO",
                    "signed": True,
                    "signature_date": "January 1, 2000",
                    "page_number": 1,
                    "source_text": (
                        "This signature block does not appear "
                        "anywhere in the document."
                    ),
                    "confidence": 0.9,
                },
                # Missing party_name must be dropped too.
                {
                    "party_name": "",
                    "signatory_name": "Someone",
                    "signatory_title": "",
                    "signed": False,
                    "signature_date": None,
                    "page_number": 1,
                    "source_text": SIGNATURE_BLOCK,
                    "confidence": 0.5,
                },
            ]
        }

    async def extract_structured_tables(
        self, *, page_context: str, table_specs: list
    ) -> dict[str, Any]:
        return {"rows": []}


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


def test_extract_signatures_grounds_and_filters() -> None:
    document_id = upload_and_extract(
        ["SIGNATURES", SIGNATURE_BLOCK],
        f"signatures-{uuid4()}.pdf",
    )

    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=SignatureStubAIProvider(),
    ):
        response = client.post(
            f"/api/documents/{document_id}/extract-signatures"
        )

    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["signatures"]) == 1

    signature = body["signatures"][0]
    assert signature["party_name"] == "ABC Technologies Inc."
    assert signature["signatory_name"] == "Jane Smith"
    assert signature["signatory_title"] == "Vice President, Sales"
    assert signature["signed"] is True
    assert signature["signature_date"] == "December 18, 2025"
    assert signature["evidence"]["page_number"] == 1

    assert len(body["warnings"]) == 1


def test_extract_signatures_requires_extracted_pages() -> None:
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
        f"/api/documents/{document_id}/extract-signatures"
    )

    assert response.status_code == 409


def test_get_signatures_reads_back_persisted_state() -> None:
    document_id = upload_and_extract(
        ["SIGNATURES", SIGNATURE_BLOCK],
        f"signatures-readback-{uuid4()}.pdf",
    )

    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=SignatureStubAIProvider(),
    ):
        client.post(
            f"/api/documents/{document_id}/extract-signatures"
        )

    response = client.get(
        f"/api/documents/{document_id}/extract-signatures"
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body["signatures"]) == 1
    assert body["signatures"][0]["party_name"] == (
        "ABC Technologies Inc."
    )
