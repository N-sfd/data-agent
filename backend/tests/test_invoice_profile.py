"""invoice@1 acceptance over the Phase D fixture set (tests/fixtures/invoices/):
each varied invoice — native, scanned+skewed, multi-page, PO-backed,
multi-charge EUR, HTML — runs the real pipeline (upload → pages/OCR →
extraction → profile) and must land in the Invoice staging workbook with
the right values, source provenance and passing arithmetic."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.v3_orchestrator import run_and_persist_v3_extraction
from app.staging.resolver import resolve_and_persist_profile

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures" / "invoices"


def _tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001
        return bool(shutil.which("tesseract"))


def _workbook(name: str) -> dict:
    path = FIXTURES / name
    content = path.read_bytes()
    mime = "text/html" if path.suffix == ".html" else "application/pdf"
    # The test DB persists across runs; keep uploads unique for dedupe.
    if mime == "text/html":
        content += f"<!-- {uuid4()} -->".encode()
    else:
        pdf = fitz.open("pdf", content)
        pdf.set_metadata({"subject": str(uuid4())})
        content = pdf.tobytes()
    upload = client.post("/api/documents/upload", files={"file": (name, content, mime)})
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]
    pages = client.post(f"/api/documents/{document_id}/extract-pages", json={"run_ocr": True})
    assert pages.status_code == 200, pages.text
    database = SessionLocal()
    try:
        document = database.get(Document, document_id)
        page_rows = list(
            database.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id))
        )
        run_and_persist_v3_extraction(database=database, document=document, pages=page_rows)
        resolve_and_persist_profile(database, document)
    finally:
        database.close()
    response = client.get(f"/api/documents/{document_id}/staging-workbook")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"]["profile_id"] == "invoice"
    return body


def _records(workbook: dict, dataset_id: str) -> list[dict]:
    dataset = next(d for d in workbook["datasets"] if d["dataset_id"] == dataset_id)
    return dataset["records"]


def _values(workbook: dict, dataset_id: str) -> dict:
    (record,) = _records(workbook, dataset_id)
    return {k.split(".")[-1]: c["value"] for k, c in record["cells"].items() if c["value"] not in (None, "")}


def _lines(workbook: dict) -> list[dict]:
    return [
        {k.split(".")[-1]: c["value"] for k, c in r["cells"].items() if c["value"] not in (None, "")}
        for r in _records(workbook, "invoice_lines")
    ]


def _qa(workbook: dict) -> dict[str, str]:
    return {
        r["cells"]["qa.check"]["value"]: r["cells"]["qa.result"]["value"]
        for r in _records(workbook, "qa_review")
    }


def _assert_arithmetic_passes(workbook: dict) -> None:
    arithmetic = {k: v for k, v in _qa(workbook).items() if k.startswith("Arithmetic")}
    assert arithmetic and set(arithmetic.values()) == {"PASS"}, arithmetic


def _assert_every_value_has_provenance(workbook: dict) -> None:
    for dataset in workbook["datasets"]:
        if dataset["role"] != "business":
            continue
        for record in dataset["records"]:
            for key, cell in record["cells"].items():
                # grounding="none" columns (Table, Category, Type, Found By) carry no provenance by design.
                if cell["value"] in (None, "") or key.endswith(("source_table", "other_values", ".category", ".value_type", ".found_by")):
                    continue
                provenance = cell["provenance"]
                assert provenance, (dataset["dataset_id"], key)
                assert provenance["source_page"] or (provenance.get("source_locator") or {}).get("dom_path"), key


def test_f1_digital_simple():
    wb = _workbook("f1_digital_simple.pdf")
    summary = _values(wb, "invoice_summary")
    assert summary["invoice_number"] == "BOS-24-1187"
    assert summary["due_date"] == "02/20/2026"
    assert summary["payment_terms"] == "Net 14"
    supplier = _values(wb, "supplier")
    assert supplier["name"] == "Brightline Office Supply Co."
    assert supplier["email"] == "orders@brightline-supply.example"
    assert _values(wb, "customer")["name"] == "Riverbend Dental Group"
    lines = _lines(wb)
    assert len(lines) == 5
    assert lines[1]["item_number"] == "TNR-26A" and lines[1]["amount"] == "$359.96"
    assert _values(wb, "totals")["invoice_amount"] == "$1,175.71"
    _assert_arithmetic_passes(wb)
    _assert_every_value_has_provenance(wb)


@pytest.mark.skipif(not _tesseract_available(), reason="Tesseract OCR not installed")
def test_f2_scanned_skewed_table_keeps_one_row_per_line_and_real_headers():
    wb = _workbook("f2_scanned_services.pdf")
    summary = _values(wb, "invoice_summary")
    assert summary["invoice_number"] == "HMS-30912"
    assert summary["due_date"] == "04/02/2026"
    supplier = _values(wb, "supplier")
    assert supplier["name"] == "HARBOR MARINE SERVICES LLC"
    assert supplier["email"] == "billing@harbormarine.example"
    lines = _lines(wb)
    assert [(l["line_number"], l["quantity"], l["amount"]) for l in lines] == [
        ("1", "6.0", "570.00"),
        ("2", "14.5", "1,595.00"),
        ("3", "3.0", "285.00"),
        ("4", "2.0", "240.00"),
    ]
    assert lines[2]["description"] == "Bilge pump replacement"
    assert _values(wb, "totals")["amount_due"] == "2,832.57"
    _assert_arithmetic_passes(wb)
    _assert_every_value_has_provenance(wb)


def test_f3_multipage_merges_pages_and_separates_uom_from_price():
    wb = _workbook("f3_multipage_parts.pdf")
    assert _values(wb, "invoice_summary")["invoice_number"] == "SIP-88410"
    assert _values(wb, "supplier")["address"] == "8800 Foundry Lane, Pueblo, CO 81001"
    assert _values(wb, "customer")["number"] == "CU-20931"
    lines = _lines(wb)
    assert len(lines) == 50
    assert lines[0]["uom"] == "EA" and lines[0]["unit_price"] == "0.42"
    assert lines[20]["uom"] == "PR" and lines[20]["unit_price"] == "212.00"
    assert lines[-1]["line_number"] == "500"
    pages = {r["cells"]["invoice.line.amount"]["provenance"]["source_page"] for r in _records(wb, "invoice_lines")}
    assert pages == {1, 2, 3}
    assert wb["qa_summary"]["needs_review"] == 0
    _assert_arithmetic_passes(wb)


def test_f4_po_backed_references_and_abbreviated_labels():
    wb = _workbook("f4_po_backed_lab.pdf")
    assert _values(wb, "invoice_summary")["invoice_number"] == "PLI-500233"
    assert _values(wb, "reference") == {
        "po_number": "PO-4500098817",
        "contract_number": "MSA-2024-117",
        "receipt_number": "GR-771034",
    }
    supplier = _values(wb, "supplier")
    assert supplier["number"] == "V-008812"
    assert supplier["tax_id"] == "33-4410982"
    assert supplier["remit_to"].startswith("Pacific Lab Instruments")
    lines = _lines(wb)
    assert [l["po_line"] for l in lines] == ["10", "20", "30", "40"]
    assert lines[3]["uom"] == "LOT"
    _assert_arithmetic_passes(wb)


def test_f5_charges_discount_and_hyphenated_codes():
    wb = _workbook("f5_complex_charges.pdf")
    summary = _values(wb, "invoice_summary")
    assert summary["invoice_number"] == "LSE-2026-0311"
    assert summary["currency"] == "EUR"
    assert _values(wb, "reference")["order_number"] == "SO-66120"
    supplier = _values(wb, "supplier")
    assert supplier["email"] == "finance@lumen-events.example"
    assert "@" not in supplier["address"]
    charges = {r["cells"]["invoice.charge.type"]["value"] for r in _records(wb, "taxes_charges")}
    assert charges == {"Discount", "Freight", "Handling", "Surcharge", "Tax"}
    totals = _values(wb, "totals")
    assert totals["amount_due"] == "€10,185.50"
    assert wb["qa_summary"]["needs_review"] == 0
    _assert_arithmetic_passes(wb)


def test_f6_html_letterhead_supplier_and_dom_provenance():
    wb = _workbook("f6_html_software.html")
    assert _values(wb, "invoice_summary")["invoice_number"] == "NSS-7731"
    supplier = _values(wb, "supplier")
    assert supplier["name"] == "Northstar Software Ltd"
    assert supplier["address"] == "14 Quayside, Newcastle upon Tyne NE1 3DX"
    customer = _values(wb, "customer")
    assert customer["bill_to_address"].startswith("Tyneside Housing Trust")
    (record,) = _records(wb, "customer")
    # The payment note after </section> is not part of "Billed To".
    assert record["cells"]["invoice.customer.bill_to_address"]["review_status"] == "Verified"
    assert len(_lines(wb)) == 3
    assert wb["qa_summary"]["needs_review"] == 0
    _assert_arithmetic_passes(wb)
    _assert_every_value_has_provenance(wb)


def test_invoice_all_fields_is_the_union_with_matching_states():
    wb = _workbook("f1_digital_simple.pdf")
    records = _records(wb, "all_fields")
    by_name = {r["cells"]["invoice.field.name"]["value"]: r["cells"] for r in records}
    number = by_name["Invoice Number"]
    assert number["invoice.field.value"]["value"] == "BOS-24-1187"
    assert number["invoice.field.category"]["value"] == "Invoice Summary"
    # A value flagged in its own tab is flagged in All Fields too.
    (summary,) = _records(wb, "invoice_summary")
    assert by_name["Invoice Date"]["invoice.field.value"]["review_status"] == summary["cells"]["invoice.invoice_date"]["review_status"] == "Needs Review"
    assert any(c["invoice.field.category"]["value"] == "Taxes / Charges" for c in by_name.values())
    import csv
    import io

    csv_rows = list(csv.reader(io.StringIO(client.get(f"/api/documents/{wb['document_id']}/staging-workbook/datasets/all_fields.csv").content.decode("utf-8-sig"))))
    assert csv_rows[0][:3] == ["Category", "Field", "Value"]
    assert len(csv_rows) - 1 == len(records) > 0
