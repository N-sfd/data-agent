"""
Coverage for the normalized structured-table extraction pipeline
(line items, price schedules, FAR/DFARS clause references, etc.) added
on top of the existing metadata/clause/signature pipelines. Follows the
same stub-AIProvider + literal-text-in-PDF grounding pattern used in
test_convera_parity.py / test_clause_extraction.py — validate_source_value
silently drops anything not verbatim on the cited page, so test PDFs must
contain the exact source_text the stub claims.
"""

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_provider import AIProvider
from app.services.contract_field_schema import FieldSpec
from app.services.contract_structured_table_schema import StructuredTableSpec


client = TestClient(app)

LINE_ITEM_TEXT = "0001 Program Management 12 MO $18,500.00 $222,000.00"
FAR_TEXT = (
    "52.212-4 Contract Terms and Conditions - Commercial Items (NOV 2023)"
)
DFARS_TEXT = (
    "252.204-7012 Safeguarding Covered Defense Information (JAN 2023). "
    "Full clause text incorporated herein."
)
FABRICATED_TEXT = "This CLIN row does not appear anywhere in the document."


class StructuredTableStubAIProvider(AIProvider):
    """Returns a scripted set of structured rows for testing."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

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
        return {"signatures": []}

    async def extract_structured_tables(
        self,
        *,
        page_context: str,
        table_specs: list[StructuredTableSpec],
    ) -> dict[str, Any]:
        return {"rows": self.rows}


def create_pdf(lines: list[str]) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()

    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=9)
        y += 20

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


def extract_structured_tables(document_id: str, rows: list[dict[str, Any]]) -> Any:
    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=StructuredTableStubAIProvider(rows),
    ):
        return client.post(
            f"/api/documents/{document_id}/extract-structured-tables"
        )


def test_line_item_extraction_and_persistence() -> None:
    document_id = upload_and_extract(
        create_pdf(["Schedule of Prices", LINE_ITEM_TEXT]),
        f"line-items-{uuid4()}.pdf",
    )

    response = extract_structured_tables(
        document_id,
        [
            {
                "family": "line_item",
                "row": {
                    "clin": "0001",
                    "description": "Program Management",
                    "quantity": "12",
                    "unit": "MO",
                    "unit_price": "18500",
                    "amount": "222000",
                    "is_maximum": "false",
                },
                "page_number": 1,
                "source_text": LINE_ITEM_TEXT,
                "confidence": 0.92,
            }
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["line_items"]) == 1
    item = body["line_items"][0]
    assert item["clin"] == "0001"
    assert item["amount"] == 222000.0
    assert item["is_maximum"] is False
    assert item["evidence"]["page_number"] == 1

    # Read-back via GET reconstructs the same persisted row.
    read_back = client.get(
        f"/api/documents/{document_id}/extract-structured-tables"
    )
    assert read_back.status_code == 200
    read_items = read_back.json()["line_items"]
    assert len(read_items) == 1
    assert read_items[0]["clin"] == "0001"
    assert read_items[0]["evidence"]["source_text"] == LINE_ITEM_TEXT


def test_far_and_dfars_clause_reference_extraction() -> None:
    document_id = upload_and_extract(
        create_pdf(["Clauses Incorporated", FAR_TEXT, DFARS_TEXT]),
        f"clause-refs-{uuid4()}.pdf",
    )

    response = extract_structured_tables(
        document_id,
        [
            {
                "family": "clause_reference",
                "row": {
                    "clause_family": "FAR",
                    "clause_number": "52.212-4",
                    "title": (
                        "Contract Terms and Conditions - "
                        "Commercial Items"
                    ),
                    "effective_date": "2023-11-01",
                },
                "page_number": 1,
                "source_text": FAR_TEXT,
                "confidence": 0.94,
            },
            {
                "family": "clause_reference",
                "row": {
                    "clause_family": "DFARS",
                    "clause_number": "252.204-7012",
                    "title": "Safeguarding Covered Defense Information",
                    "effective_date": "2023-01-01",
                    "full_text": DFARS_TEXT,
                },
                "page_number": 1,
                "source_text": DFARS_TEXT,
                "confidence": 0.9,
            },
        ],
    )

    assert response.status_code == 200, response.text
    references = response.json()["clause_references"]
    assert len(references) == 2

    far_row = next(r for r in references if r["clause_family"] == "FAR")
    dfars_row = next(r for r in references if r["clause_family"] == "DFARS")

    assert far_row["clause_number"] == "52.212-4"
    assert far_row["full_text"] is None

    assert dfars_row["clause_number"] == "252.204-7012"
    assert dfars_row["full_text"] == DFARS_TEXT


def test_empty_document_returns_all_empty_families() -> None:
    document_id = upload_and_extract(
        create_pdf(["Nothing structured here."]),
        f"empty-structured-{uuid4()}.pdf",
    )

    response = extract_structured_tables(document_id, [])

    assert response.status_code == 200, response.text
    body = response.json()

    for key in (
        "line_items",
        "performance_periods",
        "delivery_schedule",
        "key_positions",
        "funding_lines",
        "clause_references",
        "wawf_instructions",
        "insurance_requirements",
        "order_ranges",
        "amendment_history",
        "contacts",
        "addresses",
    ):
        assert body[key] == []

    assert body["warnings"] == []


def test_ungrounded_row_is_dropped_with_warning() -> None:
    document_id = upload_and_extract(
        create_pdf(["Schedule of Prices", LINE_ITEM_TEXT]),
        f"fabricated-row-{uuid4()}.pdf",
    )

    response = extract_structured_tables(
        document_id,
        [
            {
                "family": "line_item",
                "row": {
                    "clin": "9999",
                    "description": "Fabricated Item",
                },
                "page_number": 1,
                "source_text": FABRICATED_TEXT,
                "confidence": 0.5,
            }
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["line_items"] == []
    assert len(body["warnings"]) == 1
    assert "failed source validation" in body["warnings"][0]
