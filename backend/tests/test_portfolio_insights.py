from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.document_clause_reference import DocumentClauseReference
from app.models.document_contract_summary import DocumentContractSummary
from app.models.document_metadata_field import DocumentMetadataField
from app.models.document_performance_period import DocumentPerformancePeriod
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.services.portfolio_insights import build_portfolio

TODAY = date(2026, 9, 30)


def _document(database, name: str, *, status: str = "completed", document_type: str | None = None, checksum: str | None = None) -> str:
    document_id = str(uuid4())
    database.add(
        Document(
            id=document_id,
            original_filename=name,
            stored_filename=f"{document_id}.pdf",
            content_type="application/pdf",
            size_bytes=100,
            checksum_sha256=checksum or uuid4().hex,
            page_count=2,
            encrypted=False,
            status="ready",
            processing_status=status,
            document_type=document_type,
            uploaded_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            processing_duration_seconds=12.0,
        )
    )
    return document_id


@pytest.fixture
def portfolio():
    database = SessionLocal()
    ids = []
    try:
        invoice = _document(database, f"invoice-{uuid4().hex}.pdf", document_type="Invoice")
        memo = _document(database, "memo.pdf")
        contract = _document(database, "contract.pdf", document_type="Government Contract")
        failed = _document(database, "broken.pdf", status="failed")
        dup = uuid4().hex
        twin_a = _document(database, "twin.pdf", checksum=dup, document_type="Invoice")
        twin_b = _document(database, "twin copy.pdf", checksum=dup, document_type="Invoice")
        ids = [invoice, contract, failed, twin_a, twin_b, memo]
        database.flush()
        database.add(DocumentStagingWorkbook(document_id=invoice, profile_id="invoice", profile_version=1,
                                             document_family="invoice", document_family_label="Invoice", resolution_reasons=[]))
        database.add(DocumentContractSummary(document_id=contract, contract_number=None, agency_office="NAVFAC Marianas",
                                             contractor="Chugach", contract_vehicle="SB-DBMACC", naics="236220",
                                             field_provenance_json={}, confidence=0.9))
        database.add(DocumentPerformancePeriod(document_id=contract, row_index=0, period_label="Base Period",
                                               end_date="2026-11-15", confidence=0.9, evidence_json={}))
        database.add(DocumentClauseReference(document_id=contract, row_index=0, clause_family="FAR", citation_context="listing",
                                             clause_number="52.204-7", title="System for Award Management", confidence=0.9, evidence_json={}))
        database.add(DocumentMetadataField(document_id=invoice, field_group="totals", field_key="total", label="Total", value="$10", evidence_json={},
                                           original_value="$10", confidence=0.5, review_status="pending"))
        database.commit()
        yield database, ids
    finally:
        for document_id in ids:
            document = database.get(Document, document_id)
            if document is not None:
                database.delete(document)
        database.commit()
        database.close()


def test_portfolio_aggregates_only_the_given_documents(portfolio):
    database, ids = portfolio
    result = build_portfolio(database, select(Document.id).where(Document.id.in_(ids)), today=TODAY)

    assert result["totals"]["documents"] == 6
    assert result["totals"]["failed"] == 1
    mix = {item["name"]: item["count"] for item in result["document_mix"]}
    assert mix["Invoice"] == 3
    assert mix["Government Contract"] == 1
    assert mix["Unclassified"] == 2
    assert result["review"]["fields"] == 1
    assert result["review"]["low_confidence_documents"] == 1
    assert result["contracts"]["agencies"] == [{"name": "NAVFAC Marianas", "count": 1}]
    assert result["clauses"]["top"][0]["clause_number"] == "52.204-7"
    assert result["expiring"][0]["days_left"] == 46


def test_risk_register_flags_each_signal(portfolio):
    database, ids = portfolio
    risks = build_portfolio(database, select(Document.id).where(Document.id.in_(ids)), today=TODAY)["risks"]
    kinds = {item["kind"] for item in risks["items"]}
    assert {"Processing failed", "Period ending soon", "Low-confidence values", "Missing contract number", "Duplicate uploads", "Unclassified"} <= kinds
    assert risks["items"][0]["severity"] == "high"
    assert risks["by_severity"]["high"] == 2


def test_portfolio_endpoint_and_family_search(portfolio):
    database, ids = portfolio
    client = TestClient(app)
    response = client.get("/api/dashboard/portfolio")
    assert response.status_code == 200
    assert {"totals", "document_mix", "risks", "contracts"} <= set(response.json())

    invoice_name = database.get(Document, ids[0]).original_filename
    found = client.get("/api/documents/search", params={"family": "invoice", "q": invoice_name}).json()
    assert found["total"] == 1
    assert client.get("/api/documents/search", params={"family": "government_contract", "q": invoice_name}).json()["total"] == 0
    assert ids[0] in {document["document_id"] for document in found["documents"]}
    assert ids[1] not in {document["document_id"] for document in found["documents"]}
