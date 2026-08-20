"""
Parity coverage for the Convera-routed extraction path.

The shared test environment has CONVERA_ENABLED=true, so every test in
this suite already exercises `_process_pdf_via_convera` rather than the
local PyMuPDF pipeline — these tests just add explicit assertions for
behaviors the rest of the suite only covers implicitly, and for the
specific gap that used to exist (table detection was skipped entirely
on the Convera path; see document_extraction.py's
`_process_pdf_via_convera`).
"""

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_provider import AIProvider
from app.services.contract_field_schema import FieldSpec


client = TestClient(app)

TERMINATION_TEXT = (
    "Either party may terminate this Agreement upon thirty (30) "
    "days written notice."
)
SIGNATURE_BLOCK = "By: John Smith, President, Vendor Corp"


class ParityStubAIProvider(AIProvider):
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
        return {
            "clauses": [
                {
                    "clause_type": "Termination",
                    "classification": "Termination for Convenience",
                    "extracted_text": TERMINATION_TEXT,
                    "value_summary": "30 days notice",
                    "page_number": 1,
                    "confidence": 0.9,
                }
            ]
        }

    async def extract_signatures(
        self, *, page_context: str
    ) -> dict[str, Any]:
        return {
            "signatures": [
                {
                    "party_name": "Vendor Corp",
                    "signatory_name": "John Smith",
                    "signatory_title": "President",
                    "signed": True,
                    "signature_date": "2026-07-15",
                    "page_number": 1,
                    "source_text": SIGNATURE_BLOCK,
                    "confidence": 0.9,
                }
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
        page.insert_text((72, y), line)
        y += 20

    content = pdf.tobytes()
    pdf.close()

    return content


def create_generic_table_pdf() -> bytes:
    """A ruled table whose headers don't match the role/rate keywords
    used for rate-card detection — should classify as "generic"."""

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
        ("Milestone", "Due Date"),
        ("Kickoff", "2026-01-15"),
        ("Delivery", "2026-06-30"),
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


def analyze(document_id: str) -> dict:
    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=ParityStubAIProvider(),
    ):
        response = client.post(
            f"/api/documents/{document_id}/analyze-contract"
        )

    assert response.status_code == 200, response.text

    return response.json()


def test_convera_routes_extraction_method() -> None:
    document_id = upload_and_extract(
        create_pdf(["Contract Title: Convera Routing Check"]),
        f"convera-routing-{uuid4()}.pdf",
    )

    pages = client.get(f"/api/documents/{document_id}/pages")
    assert pages.status_code == 200
    assert pages.json()[0]["extraction_method"] == "convera"


def test_generic_table_type_detection() -> None:
    document_id = upload_and_extract(
        create_generic_table_pdf(),
        f"generic-table-{uuid4()}.pdf",
    )

    response = client.post(
        f"/api/documents/{document_id}/extract-tables"
    )
    assert response.status_code == 200

    tables = response.json()["tables"]
    assert len(tables) == 1
    assert tables[0]["table_type"] == "generic"
    assert tables[0]["rate_card_rows"] == []


def test_page_provenance_on_convera_path() -> None:
    document_id = upload_and_extract(
        create_pdf(["Contract Title: Provenance Check"]),
        f"provenance-{uuid4()}.pdf",
    )
    result = analyze(document_id)

    title_field = next(
        field
        for field in result["metadata_fields"]
        if field["field_key"] == "contract_title"
    )

    assert title_field["evidence"]["page_number"] == 1
    assert "page 1" in title_field["evidence"]["source_reference"]


def test_contract_value_extracted_on_convera_path() -> None:
    document_id = upload_and_extract(
        create_pdf(
            [
                "Contract Title: Value Check",
                "Contract Value: $1,250,000.00",
            ]
        ),
        f"contract-value-{uuid4()}.pdf",
    )
    result = analyze(document_id)

    value_field = next(
        field
        for field in result["metadata_fields"]
        if field["field_key"] == "contract_value"
    )

    assert "1,250,000" in value_field["value"]


def test_clause_extraction_on_convera_path() -> None:
    document_id = upload_and_extract(
        create_pdf(
            ["Contract Title: Clause Check", TERMINATION_TEXT]
        ),
        f"clause-parity-{uuid4()}.pdf",
    )

    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=ParityStubAIProvider(),
    ):
        response = client.post(
            f"/api/documents/{document_id}/extract-clauses"
        )

    assert response.status_code == 200
    clauses = response.json()["clauses"]
    assert len(clauses) == 1
    assert clauses[0]["clause_type"] == "Termination"


def test_signature_extraction_on_convera_path() -> None:
    document_id = upload_and_extract(
        create_pdf(
            ["Contract Title: Signature Check", SIGNATURE_BLOCK]
        ),
        f"signature-parity-{uuid4()}.pdf",
    )

    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=ParityStubAIProvider(),
    ):
        response = client.post(
            f"/api/documents/{document_id}/extract-signatures"
        )

    assert response.status_code == 200
    signatures = response.json()["signatures"]
    assert len(signatures) == 1
    assert signatures[0]["signatory_name"] == "John Smith"


def test_scanned_image_only_page_does_not_crash_table_detection() -> (
    None
):
    """An image-only page (no real text/vector content) should make
    pdfplumber find zero tables rather than raising — the Convera path
    wraps table detection in a try/except for exactly this case."""

    pdf = fitz.open()
    page = pdf.new_page()

    # A blank filled rectangle stands in for a scanned page image —
    # no extractable text or ruling lines for pdfplumber to key off.
    page.draw_rect(page.rect, fill=(0.9, 0.9, 0.9))

    content = pdf.tobytes()
    pdf.close()

    document_id = upload_and_extract(
        content, f"scanned-{uuid4()}.pdf"
    )

    response = client.post(
        f"/api/documents/{document_id}/extract-tables"
    )

    assert response.status_code == 200
    assert response.json()["tables"] == []
