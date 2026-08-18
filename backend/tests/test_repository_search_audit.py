from typing import Any
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_provider import AIProvider
from app.services.contract_field_schema import FieldSpec


client = TestClient(app)


class RepoSearchStubAIProvider(AIProvider):
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
        return_value=RepoSearchStubAIProvider(),
    ):
        response = client.post(
            f"/api/documents/{document_id}/analyze-contract"
        )

    assert response.status_code == 200, response.text

    return response.json()


def test_search_matches_by_filename() -> None:
    unique = str(uuid4())
    document_id = upload(
        ["Contract Title: Master Services Agreement"],
        f"unique-marker-{unique}.pdf",
    )
    extract_pages(document_id)

    response = client.get(
        "/api/documents/search", params={"q": unique}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["documents"][0]["document_id"] == document_id


def test_search_matches_by_contract_number() -> None:
    unique = str(uuid4()).replace("-", "")[:12]
    document_id = upload(
        [
            "Contract Title: Master Services Agreement",
            f"Contract Number: MSA-2026-{unique}",
        ],
        f"search-number-{uuid4()}.pdf",
    )
    extract_pages(document_id)
    analyze(document_id)

    response = client.get(
        "/api/documents/search", params={"q": unique}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["total"] >= 1
    assert any(
        doc["document_id"] == document_id
        for doc in body["documents"]
    )


def test_search_no_query_returns_paginated_all_documents() -> None:
    upload(["Some content"], f"paginate-a-{uuid4()}.pdf")
    upload(["Some content"], f"paginate-b-{uuid4()}.pdf")

    response = client.get(
        "/api/documents/search", params={"limit": 1, "offset": 0}
    )
    assert response.status_code == 200

    body = response.json()
    assert len(body["documents"]) == 1
    assert body["total"] >= 2


def test_search_unmatched_query_returns_empty() -> None:
    response = client.get(
        "/api/documents/search",
        params={"q": f"no-such-document-{uuid4()}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 0
    assert body["documents"] == []


def test_global_audit_log_reflects_field_review() -> None:
    document_id = upload(
        [
            "Contract Title: Master Services Agreement",
            f"Governing Law: State of Delaware {uuid4()}",
        ],
        f"audit-{uuid4()}.pdf",
    )
    extract_pages(document_id)
    analyzed = analyze(document_id)

    first_field_key = analyzed["metadata_fields"][0]["field_key"]

    client.post(
        f"/api/documents/{document_id}/metadata-fields/"
        f"{first_field_key}/review",
        json={"action": "accept", "changed_by": "Audit Tester"},
    )

    response = client.get(
        "/api/documents/audit-log", params={"limit": 50}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["total"] >= 1

    matching = [
        entry
        for entry in body["entries"]
        if entry["document_id"] == document_id
        and entry["field_key"] == first_field_key
    ]
    assert len(matching) == 1
    assert matching[0]["action"] == "accept"
    assert matching[0]["changed_by"] == "Audit Tester"
    assert matching[0]["document_filename"].startswith("audit-")
