"""Export / API integrity — reviewed vs machine values.

Certifies:
- Rich JSON preserves extracted_value + effective value + review_status
- Business CSV uses effective value as primary ``value``
- Oracle preview excludes pending/rejected from authoritative payload
- extract-results exposes governance fields after reopen
"""

from __future__ import annotations

from uuid import uuid4

import fitz
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.main import app
from app.models.document_metadata_field import DocumentMetadataField
from app.services.reviewed_export import (
    AUTHORITATIVE_REVIEW_STATUSES,
    field_to_export_record,
)

client = TestClient(app)


def _pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Total Amount: $120,000", fontsize=10)
    content = pdf.tobytes()
    pdf.close()
    return content


def _upload() -> str:
    response = client.post(
        "/api/documents/upload",
        files={"file": (f"export-{uuid4()}.pdf", _pdf(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def _seed(
    database: Session,
    document_id: str,
    *,
    key: str,
    label: str,
    value: str,
    review_status: str,
    machine_value: str | None = None,
    confidence: float = 0.81,
) -> None:
    database.add(
        DocumentMetadataField(
            document_id=document_id,
            field_group="Financial",
            field_key=key,
            label=label,
            value=value,
            original_value=machine_value or value,
            confidence=confidence,
            confidence_band="high" if confidence >= 0.85 else "medium",
            value_type="currency",
            extraction_method="label_value",
            evidence_json={
                "page_number": 8,
                "source_text": f"{label}: {machine_value or value}",
                "source_reference": "page 8",
                "machine_value": machine_value or value,
                "reviewed_value": value if review_status == "edited" else None,
                "validation": {"status": "passed", "checks": [], "warnings": []},
                "validation_status": "passed",
            },
            verified=True,
            review_status=review_status,
            extraction_source="target",
            human_approved=review_status in AUTHORITATIVE_REVIEW_STATUSES,
        )
    )


def test_export_json_preserves_machine_and_reviewed_values() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed(
            database,
            document_id,
            key="total_amount",
            label="Total Amount",
            value="$125,000",
            review_status="edited",
            machine_value="$120,000",
        )
        database.commit()
    finally:
        database.close()

    response = client.get(f"/api/documents/{document_id}/export")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == document_id
    assert body["field_count"] == 1
    field = body["fields"][0]
    assert field == {
        "field": "Total Amount",
        "field_key": "total_amount",
        "field_group": "Financial",
        "extracted_value": "$120,000",
        "value": "$125,000",
        "review_status": "edited",
        "confidence": 0.81,
        "validation": {"status": "passed"},
        "source": {"page": 8},
        "authoritative": True,
    }


def test_export_csv_uses_effective_reviewed_value() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed(
            database,
            document_id,
            key="total_amount",
            label="Total Amount",
            value="$125,000",
            review_status="edited",
            machine_value="$120,000",
        )
        database.commit()
    finally:
        database.close()

    response = client.get(f"/api/documents/{document_id}/export.csv")
    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers["content-type"]
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("field,value,extracted_value,review_status")
    assert "$125,000" in lines[1]
    assert "$120,000" in lines[1]
    assert "edited" in lines[1]


def test_oracle_payload_excludes_pending_and_rejected() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed(
            database,
            document_id,
            key="total_amount",
            label="Total Amount",
            value="$125,000",
            review_status="edited",
            machine_value="$120,000",
        )
        _seed(
            database,
            document_id,
            key="vendor_name",
            label="Vendor Name",
            value="Acme Corp",
            review_status="pending",
            machine_value="Acme Corp",
        )
        _seed(
            database,
            document_id,
            key="bad_field",
            label="Bad Field",
            value="nope",
            review_status="rejected",
            machine_value="nope",
        )
        database.commit()
    finally:
        database.close()

    response = client.get(f"/api/documents/{document_id}/oracle-payload")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "preview"
    assert body["send_allowed"] is False
    assert body["authoritative_count"] == 1
    assert body["skipped_count"] == 2
    assert body["ready_to_send"] is False
    assert set(body["contract_header"].keys()) == {"total_amount"}
    assert body["contract_header"]["total_amount"] == "$125,000"
    assert all(
        field["review_status"] in AUTHORITATIVE_REVIEW_STATUSES
        for field in body["fields"]
    )
    skipped_statuses = {item["review_status"] for item in body["skipped"]}
    assert skipped_statuses == {"pending", "rejected"}
    assert "pending" in body["excluded_statuses"]
    assert "rejected" in body["excluded_statuses"]


def test_oracle_authoritative_only_query_on_export() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed(
            database,
            document_id,
            key="total_amount",
            label="Total Amount",
            value="$125,000",
            review_status="accepted",
            machine_value="$125,000",
        )
        _seed(
            database,
            document_id,
            key="pending_field",
            label="Pending Field",
            value="x",
            review_status="pending",
        )
        database.commit()
    finally:
        database.close()

    response = client.get(
        f"/api/documents/{document_id}/export",
        params={"authoritative_only": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["field_count"] == 1
    assert body["fields"][0]["field_key"] == "total_amount"
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["review_status"] == "pending"


def test_extract_results_exposes_extracted_value_and_review_status() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed(
            database,
            document_id,
            key="total_amount",
            label="Total Amount",
            value="$125,000",
            review_status="edited",
            machine_value="$120,000",
        )
        database.commit()
    finally:
        database.close()

    response = client.get(f"/api/documents/{document_id}/extract-results")
    assert response.status_code == 200, response.text
    scalar = response.json()["scalars"][0]
    assert scalar["value"] == "$125,000"
    assert scalar["extracted_value"] == "$120,000"
    assert scalar["review_status"] == "edited"


def test_field_to_export_record_helper_shape() -> None:
    field = DocumentMetadataField(
        document_id="x",
        field_group="Financial",
        field_key="total_amount",
        label="Total Amount",
        value="$125,000",
        original_value="$120,000",
        confidence=0.81,
        confidence_band="medium",
        value_type="currency",
        extraction_method="label_value",
        evidence_json={
            "page_number": 8,
            "machine_value": "$120,000",
            "validation": {"status": "passed"},
        },
        verified=True,
        review_status="edited",
        extraction_source="target",
    )
    record = field_to_export_record(field)
    assert record["extracted_value"] == "$120,000"
    assert record["value"] == "$125,000"
    assert record["source"]["page"] == 8
    assert record["authoritative"] is True
