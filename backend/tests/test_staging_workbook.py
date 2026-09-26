"""Professional Staging Workbook foundation (app/staging/): validation →
three states, registry/resolver, engine guarantees, and the API."""

import re
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.services.v3_orchestrator import run_and_persist_v3_extraction
from app.staging import registry
from app.staging.engine import assemble_workbook, evidence_literal
from app.staging.models import ProcessingMetadata
from app.staging.profile import (
    AdapterResult,
    DatasetDefinition,
    FieldDefinition,
    FieldRule,
    RawRecord,
    StagingProfile,
)
from app.staging.profiles.contract_v3 import CONTRACT_SUMMARY
from app.staging.provenance import anchor_from_evidence, make_provenance
from app.staging.resolver import resolve_and_persist_profile
from app.staging.validation import evaluate_cell, value_in_evidence

client = TestClient(app)


def _doc(**overrides):
    fields = dict(
        id="doc-1",
        original_filename="Contract.pdf",
        stored_filename="doc-1.pdf",
        ingestion_provenance=None,
    )
    fields.update(overrides)
    return Document(**fields)


def _prov(evidence: str | None, page: int = 11):
    return make_provenance(_doc(), page=page, evidence=evidence)


MIN_GUARANTEE = CONTRACT_SUMMARY.fields[7]
SIZE_STANDARD = CONTRACT_SUMMARY.fields[13]


# --- validation: the three states ---------------------------------------


def test_grounding_uses_token_boundaries_and_numeric_equality():
    assert value_in_evidence("$2,500.00", "minimum ... is \n$2,500.00 per contract", "money")
    assert value_in_evidence(2500.0, "Funding Line 2,500.00", "money")
    # A truncated value is not supported by the longer token.
    assert not value_in_evidence("$47.0", "size standard is $47.0M (541330)", "text")
    assert value_in_evidence("47QRCA25DSF07", "CONTRACT NUMBER -> 47QRCA25DSF07", "code")


def test_minimum_guarantee_verified_only_when_evidence_supports_it():
    evidence = "The minimum guaranteed award amount for this IDIQ contract is $2,500.00."
    _, status, _ = evaluate_cell(MIN_GUARANTEE, "$2,500.00", _prov(evidence), record_flagged=False)
    assert status == "Verified"


def test_zero_dollar_minimum_guarantee_is_never_verified():
    # The motivating case: a perfectly-read "$0.00" from a CLIN line is not
    # a minimum guarantee, however confident the OCR was.
    _, status, reasons = evaluate_cell(
        MIN_GUARANTEE, "$0.00", _prov("10300 Research and Development 0.00"), record_flagged=False
    )
    assert status == "Needs Review"
    assert any("zero" in r or "minimum" in r for r in reasons)


def test_truncated_value_needs_review():
    _, status, reasons = evaluate_cell(
        SIZE_STANDARD, "$47.0", _prov("the largest size standard is $47.0M"), record_flagged=False
    )
    assert status == "Needs Review"
    assert "Value does not appear as-is in its source evidence." in reasons


def test_expected_empty_field_is_missing_optional_is_blank():
    optional = FieldDefinition("x.fob", "fob", "FOB")
    assert evaluate_cell(MIN_GUARANTEE, None, None, record_flagged=False)[1] == "Missing"
    assert evaluate_cell(optional, None, None, record_flagged=False)[1] is None


def test_flagged_record_never_has_verified_cells():
    field = FieldDefinition("x.clin", "clin", "CLIN", "code")
    _, status, _ = evaluate_cell(field, "10301", _prov("10301 RD 0.00"), record_flagged=True)
    assert status == "Needs Review"


def test_value_without_evidence_needs_review():
    field = FieldDefinition("x.v", "v", "V")
    assert evaluate_cell(field, "abc", _prov(None), record_flagged=False)[1] == "Needs Review"


def test_derived_value_needs_evidence_but_not_verbatim():
    field = FieldDefinition(
        "x.base", "base", "Base Period", grounding="derived",
        rules=(FieldRule("evidence_mentions", terms=("base",)),),
    )
    evidence = "a five year base period of performance"
    assert evaluate_cell(field, "5 years", _prov(evidence), record_flagged=False)[1] == "Verified"


# --- provenance helpers ---------------------------------------------------


def test_anchor_is_form_label_for_synthetic_label_value_evidence():
    assert anchor_from_evidence("CONTRACT NUMBER -> 47QRCA25DSF07") == "CONTRACT NUMBER"
    assert anchor_from_evidence("line one\nline two") == "line one"


def test_evidence_literal_returns_source_spelling_for_numbers():
    assert evidence_literal(2500.0, "Funding Line 2,500.00", "money") == "2,500.00"
    assert evidence_literal("GSA OASIS+ MAC", "GSA  OASIS+\nMAC Program", "text") == "GSA  OASIS+\nMAC"


# --- registry --------------------------------------------------------------


def test_builtin_profiles_are_versioned():
    keys = {p.key for p in registry.all_profiles()}
    assert {"contract_v3@1", "generic_business_document@1"} <= keys


def test_invoice_family_has_no_profile_yet_so_it_is_not_forced_into_contract():
    assert registry.profile_for_family("invoice") is None
    assert registry.profile_for_family("government_contract").profile_id == "contract_v3"


@pytest.mark.parametrize("profile", registry.all_profiles(), ids=lambda p: p.key)
def test_canonical_fields_are_stable_ids_not_display_labels(profile):
    seen = set()
    for dataset in profile.datasets:
        for field in dataset.fields:
            assert re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", field.canonical_field)
            assert field.canonical_field not in seen or dataset.dataset_id == "all_fields"
            seen.add(field.canonical_field)


# --- engine guarantees ------------------------------------------------------


def _tiny_profile(adapter, **overrides) -> StagingProfile:
    fields = dict(
        profile_id="tiny",
        profile_version=1,
        display_name="Tiny",
        description="",
        document_families=(),
        datasets=(
            DatasetDefinition(
                "summary", "Summary", "single",
                (FieldDefinition("tiny.number", "number", "Number", "code", expected=True),),
            ),
            DatasetDefinition(
                "lines", "Lines", "repeating",
                (FieldDefinition("tiny.line.amount", "amount", "Amount", "money"),),
            ),
            DatasetDefinition(
                "qa", "QA", "repeating",
                tuple(
                    FieldDefinition(f"qa.{k}", k, k, grounding="none")
                    for k in ("qa_check", "result", "details", "action")
                ),
                role="qa",
            ),
        ),
        adapter=adapter,
        export_capabilities=(),
        auto_qa_dataset="qa",
    )
    fields.update(overrides)
    return StagingProfile(**fields)


def _assemble(records, provenance=None):
    profile = _tiny_profile(lambda db, doc: None)
    return assemble_workbook(
        profile=profile,
        document=_doc(),
        adapter_result=AdapterResult(records=records, outcome_provenance=provenance),
        metadata=ProcessingMetadata(),
    )


def test_empty_single_dataset_renders_missing_fields_and_explicit_outcome():
    workbook = _assemble({}, {"v3_extraction": {"status": "completed"}})
    summary = workbook.datasets[0]
    assert summary.records[0].cells["tiny.number"].review_status == "Missing"
    assert workbook.outcome.status == "no_supported_fields"
    assert workbook.qa_summary.missing == 1


def test_auto_qa_summarizes_validated_datasets():
    line = RawRecord(
        record_id="l1",
        values={"amount": 5.0},
        provenance=make_provenance(_doc(), page=1, evidence="Item 1 5.00", anchor="Item 1"),
    )
    workbook = _assemble({"lines": [line]}, {"v3_extraction": {"status": "completed"}})
    qa = {r.cells["qa.qa_check"].value: r for r in workbook.datasets[2].records}
    assert qa["Lines"].cells["qa.result"].value == "PASS"
    assert qa["Lines"].links_to_dataset == "lines"
    assert qa["Summary"].cells["qa.result"].value == "NOT FOUND"
    # Cell provenance carries the exact source spelling for highlighting.
    cell = workbook.datasets[1].records[0].cells["tiny.line.amount"]
    assert cell.provenance.highlight_text == "5.00"
    assert cell.provenance.anchor_text == "Item 1"


# --- API + persistence ------------------------------------------------------


def _upload(lines: list[str]) -> str:
    pdf = fitz.open()
    page = pdf.new_page()
    for index, text in enumerate(lines):
        page.insert_text((72, 72 + 16 * index), text, fontsize=10)
    response = client.post(
        "/api/documents/upload",
        files={"file": (f"staging-{uuid4()}.pdf", pdf.tobytes(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]
    extracted = client.post(
        f"/api/documents/{document_id}/extract-pages", json={"run_ocr": False}
    )
    assert extracted.status_code == 200, extracted.text
    return document_id


def _run_v3(document_id: str) -> None:
    database = SessionLocal()
    try:
        document = database.get(Document, document_id)
        pages = list(
            database.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id))
        )
        run_and_persist_v3_extraction(database=database, document=document, pages=pages)
        resolve_and_persist_profile(database, document)
    finally:
        database.close()


def test_invoice_resolves_to_generic_profile_and_is_never_blank():
    document_id = _upload(
        [
            "INVOICE",
            "Invoice Number: INV-1001   Invoice Date: 03/14/2025",
            "Bill To: Cascade Water Authority   Remit To: Northwind Supply",
            "Amount Due: $1,200.00",
            "Email: billing@northwind.example",
        ]
    )
    _run_v3(document_id)

    response = client.get(f"/api/documents/{document_id}/staging-workbook")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"]["profile_id"] == "generic_business_document"
    assert body["profile"]["profile_version"] == 1
    assert body["processing_metadata"]["document_family"] == "invoice"
    assert body["outcome"]["status"] != "pending"
    dataset_ids = [d["dataset_id"] for d in body["datasets"]]
    assert dataset_ids[0] == "document_summary"
    assert "qa_review" in dataset_ids
    summary = body["datasets"][0]["records"][0]["cells"]
    assert summary["document.document_type"]["value"] == "Invoice"

    # Exports declared by the profile work.
    for capability in body["profile"]["export_capabilities"]:
        assert "{document_id}" not in capability["href"]
        exported = client.get(capability["href"])
        assert exported.status_code == 200, capability["href"]


def test_profile_is_pinned_and_survives_reopen():
    document_id = _upload(["Some memo", "Nothing to see here"])
    _run_v3(document_id)
    first = client.get(f"/api/documents/{document_id}/staging-workbook").json()
    second = client.get(f"/api/documents/{document_id}/staging-workbook").json()
    assert first["profile"]["profile_id"] == second["profile"]["profile_id"]

    database = SessionLocal()
    try:
        rows = database.scalars(
            select(DocumentStagingWorkbook).where(DocumentStagingWorkbook.document_id == document_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].profile_version == 1
    finally:
        database.close()


def test_document_processed_before_profiles_is_pinned_on_first_read():
    document_id = _upload(["Plain document"])
    # No resolve step: simulates a document extracted before phase B.
    response = client.get(f"/api/documents/{document_id}/staging-workbook")
    assert response.status_code == 200
    database = SessionLocal()
    try:
        assert database.scalars(
            select(DocumentStagingWorkbook).where(DocumentStagingWorkbook.document_id == document_id)
        ).first() is not None
    finally:
        database.close()


def test_unknown_document_is_404():
    assert client.get(f"/api/documents/{uuid4()}/staging-workbook").status_code == 404


def test_unknown_dataset_csv_is_404():
    document_id = _upload(["Plain document"])
    response = client.get(f"/api/documents/{document_id}/staging-workbook/datasets/nope.csv")
    assert response.status_code == 404


def test_profiles_endpoint_lists_registered_profiles():
    response = client.get("/api/staging-profiles")
    assert response.status_code == 200
    ids = {(p["profile_id"], p["profile_version"]) for p in response.json()}
    assert ("contract_v3", 1) in ids and ("generic_business_document", 1) in ids


# --- cell-level source highlighting -----------------------------------------


def test_highlight_prefers_value_on_anchor_line_over_nearer_other_row():
    from app.api.page_extraction import locate_highlight

    pdf = fitz.open()
    page = pdf.new_page(width=612, height=792)
    # Two CLIN rows; row 10304's amount is closer (straight-line) to the
    # 10305 CLIN number than 10305's own right-aligned amount.
    page.insert_text((24, 640), "10304", fontsize=9)
    page.insert_text((175, 640), "0.00", fontsize=9)
    page.insert_text((24, 675), "10305", fontsize=9)
    page.insert_text((557, 675), "0.00", fontsize=9)

    rect = locate_highlight(page, highlight="0.00", anchor="10305", region=None)
    assert rect is not None and rect.x0 > 500


def test_highlight_falls_back_to_anchor_when_value_absent():
    from app.api.page_extraction import locate_highlight

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 100), "CONTRACT NUMBER", fontsize=10)
    rect = locate_highlight(page, highlight="not on page", anchor="CONTRACT NUMBER", region=None)
    assert rect is not None and abs(rect.y1 - 100) < 5
