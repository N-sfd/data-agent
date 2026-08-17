from typing import Any
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_provider import AIProvider
from app.services.contract_field_schema import FieldSpec


client = TestClient(app)


class CustomFieldStubAIProvider(AIProvider):
    """Resolves a custom field the deterministic pass can't find."""

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
        fields = []

        for spec in field_specs:
            if spec.group == "Custom":
                fields.append(
                    {
                        "field_key": spec.key,
                        "value": "$5,000,000",
                        "page_number": 1,
                        "source_text": (
                            "Cyber liability coverage of $5,000,000"
                        ),
                        "confidence": 0.85,
                    }
                )

        return {"fields": fields}

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


def test_create_model_and_add_field() -> None:
    create_response = client.post(
        "/api/extraction-models",
        json={
            "name": f"Supplier Agreement {uuid4()}",
            "description": "Fields for supplier agreements",
        },
    )

    assert create_response.status_code == 201, create_response.text
    model = create_response.json()
    assert model["fields"] == []

    field_response = client.post(
        f"/api/extraction-models/{model['id']}/fields",
        json={
            "field_name": "Cyber Insurance Limit",
            "description": (
                "Extract the maximum cyber liability insurance "
                "coverage required under the agreement."
            ),
            "data_type": "currency",
        },
    )

    assert field_response.status_code == 201, field_response.text
    body = field_response.json()

    assert len(body["fields"]) == 1
    assert body["fields"][0]["field_name"] == "Cyber Insurance Limit"
    assert body["fields"][0]["data_type"] == "currency"


def test_list_models_includes_created_model() -> None:
    unique_name = f"Custom List Model {uuid4()}"

    client.post(
        "/api/extraction-models",
        json={"name": unique_name, "description": ""},
    )

    response = client.get("/api/extraction-models")
    assert response.status_code == 200

    names = [model["name"] for model in response.json()]
    assert unique_name in names


def test_delete_field_and_model() -> None:
    model = client.post(
        "/api/extraction-models",
        json={"name": f"Deletable {uuid4()}", "description": ""},
    ).json()

    field = client.post(
        f"/api/extraction-models/{model['id']}/fields",
        json={
            "field_name": "Temp Field",
            "description": "",
            "data_type": "text",
        },
    ).json()["fields"][0]

    delete_field_response = client.delete(
        f"/api/extraction-models/{model['id']}/fields/{field['id']}"
    )
    assert delete_field_response.status_code == 200
    assert delete_field_response.json()["fields"] == []

    delete_model_response = client.delete(
        f"/api/extraction-models/{model['id']}"
    )
    assert delete_model_response.status_code == 204

    list_response = client.get("/api/extraction-models")
    ids = [m["id"] for m in list_response.json()]
    assert model["id"] not in ids


def test_custom_field_resolves_through_analyze_contract() -> None:
    model = client.post(
        "/api/extraction-models",
        json={
            "name": f"Supplier Agreement {uuid4()}",
            "description": "",
        },
    ).json()

    client.post(
        f"/api/extraction-models/{model['id']}/fields",
        json={
            "field_name": "Cyber Insurance Limit",
            "description": "Max cyber liability coverage.",
            "data_type": "currency",
        },
    )

    document_id = upload_and_extract(
        [
            "Contract Title: Supplier Agreement",
            "Cyber liability coverage of $5,000,000",
        ],
        f"custom-field-{uuid4()}.pdf",
    )

    with patch(
        "app.api.contract_analysis.create_ai_provider",
        return_value=CustomFieldStubAIProvider(),
    ):
        response = client.post(
            f"/api/documents/{document_id}/analyze-contract",
            json={"extraction_model_id": model["id"]},
        )

    assert response.status_code == 200, response.text
    body = response.json()

    custom_fields = [
        field
        for field in body["metadata_fields"]
        if field["field_group"] == "Custom"
    ]

    assert len(custom_fields) == 1
    assert custom_fields[0]["label"] == "Cyber Insurance Limit"
    assert custom_fields[0]["value"] == "$5,000,000"
    assert custom_fields[0]["extraction_method"] == "ai"
