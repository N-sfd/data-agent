"""Source-adaptive contract structure: cover forms, schedule tables and
clause context, on the three regression contracts plus synthetic layouts.

N4019223D2803 (Navy SF1442), 47QRCA25DSF07 (GSA SF33 + continuation
sheets) and FA300224C0008 (Air Force SF33) are real contracts kept out of
git: their tests skip where the files are absent. Expected values were
checked against the PDFs; N4019223D2803's cover values are the ones the
user confirmed (Performance Start = "Award", the only box marked).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.contract_structure.builder import structure_from_pages
from app.contract_structure.clauses import (
    BY_REFERENCE,
    IN_FULL_TEXT,
    incorporation_heading,
    read_clauses,
)
from app.contract_structure.lines import PageLines, Word, pdf_page_lines
from app.contract_structure.schedule import read_schedule_tables
from app.database.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.line_model import LogicalLine
from app.services.v3_orchestrator import run_and_persist_v3_extraction
from app.staging.resolver import resolve_and_persist_profile

REGRESSION = Path(__file__).resolve().parents[2] / "reference" / "regression"
NAVY = REGRESSION / "SF1442 Award_N4019223D2803.pdf"
GSA = REGRESSION / "Contract_47QRCA25DSF07 (2).pdf"
AIR_FORCE = REGRESSION / "Contract - FA300224C0008 (2).pdf"

client = TestClient(app)


def _requires(path: Path):
    return pytest.mark.skipif(not path.exists(), reason=f"{path.name} not present (real contract, not in git)")


def _structure(path: Path) -> dict:
    return structure_from_pages(pdf_page_lines(fitz.open(path)))


def _fields(structure: dict) -> dict[str, dict]:
    return {field["field_id"]: field for field in structure["fields"]}


def _clauses(structure: dict) -> dict[str, list[dict]]:
    by_number: dict[str, list[dict]] = {}
    for clause in structure["clauses"]:
        by_number.setdefault(clause["clause_number"], []).append(clause)
    return by_number


def _counts(structure: dict) -> Counter:
    return Counter((c["regulation"], c["incorporation_type"]) for c in structure["clauses"])


# --- N4019223D2803 (SF1442) ------------------------------------------------------


@pytest.fixture(scope="module")
def navy() -> dict:
    return _structure(NAVY)


@_requires(NAVY)
def test_navy_sf1442_fields_keep_source_labels(navy):
    fields = _fields(navy)
    expected = {
        "contract.solicitation_number": ("1. SOLICITATION NO.", "N4019221R28000019"),
        "contract.solicitation_type": ("2. TYPE OF SOLICITATION", "Negotiated (RFP)"),
        "contract.date_issued": ("3. DATE ISSUED", "29-Sep-2023"),
        "contract.page_of_pages": ("PAGE OF PAGES", "1 of 33"),
        "contract.contract_number": ("4. CONTRACT NO.", "N4019223D2803"),
        "contract.requisition_number": ("5. REQUISITION/PURCHASE REQUEST NO.", "ACQR5858342"),
        "contract.issued_by_code": ("7. ISSUED BY — CODE", "N40192"),
        "contract.issued_by": ("7. ISSUED BY", "COMMANDING OFFICER - NAVFAC MARIANAS\nMAR CORE DC\nPSC 455, BOX 195\nFPO AP 96540-2937"),
        "contract.address_offer_to": ("8. ADDRESS OFFER TO", "See Item 7"),
        "contract.information_contact_name": ("9. FOR INFORMATION CALL — A. NAME", "DORIS CASTRO"),
        "contract.information_contact_telephone": ("9. FOR INFORMATION CALL — B. TELEPHONE NO.", "671-339-8465"),
        "contract.performance_start": ("Performance Start", "Award"),
        "contract.bonds_required": ("Performance and Payment Bonds Required", "Yes"),
        "contract.bond_due_days": ("Bonds Due (Calendar Days)", "10 calendar days"),
        "contract.offer_due_date": ("Offer Due Date", "24 Mar 2023"),
        "contract.offer_due_time": ("Offer Due Time", "04:30 PM"),
        "contract.offer_guarantee_required": ("Offer Guarantee Required", "Yes"),
        "contract.acceptance_period": ("Government Acceptance Period", "120 calendar days"),
        "contract.award_amount": ("22. AMOUNT", "$600,000,000.00"),
        "contract.contracting_officer": ("31A. NAME OF CONTRACTING OFFICER", "DORIS CASTRO / SUPVY CONTRACT SPECIALIST"),
        "contract.award_date": ("31C. AWARD DATE", "29-Sep-2023"),
    }
    for field_id, (label, value) in expected.items():
        assert (fields[field_id]["label"], fields[field_id]["value"]) == (label, value), field_id
    title = fields["contract.solicitation_title"]["value"]
    assert title.startswith("REQUEST FOR PROPOSAL N40192-21-R-2800") and title.endswith("VARIOUS LOCATIONS, GUAM")
    # A blank box yields no field.
    assert "contract.project_number" not in fields


@_requires(NAVY)
def test_navy_line_items_keep_source_headings_across_pages(navy):
    table = navy["tables"]["line_items"]
    assert [c["header"] for c in table["columns"]] == [
        "ITEM NO", "SUPPLIES/SERVICES", "MAX QUANTITY", "UNIT", "UNIT PRICE", "MAX AMOUNT",
    ]
    records = table["records"]
    assert [r["values"]["item_number"] for r in records] == ["0001", "0002", "0003", "0004"]
    assert [r["page"] for r in records] == [4, 5, 6, 7]
    first = records[0]["values"]
    assert (first["quantity"], first["unit"], first["unit_price"], first["amount"]) == (
        "600,000,000", "Each", "$1.00", "$600,000,000.00 NTE",
    )
    assert first["description"].startswith("Base Period - SB-DBMACC")
    # Repeated page headers and per-page totals are never data.
    for record in records:
        assert "ITEM NO" not in record["values"]["description"]
        assert "NET AMT" not in " ".join(record["values"].values())


@_requires(NAVY)
def test_navy_delivery_information(navy):
    table = navy["tables"]["delivery_information"]
    assert [c["header"] for c in table["columns"]] == ["CLIN", "DELIVERY DATE", "QUANTITY", "SHIP TO ADDRESS", "DODAAC / CAGE"]
    first = table["records"][0]["values"]
    assert first["clin"] == "0001"
    assert first["delivery_date"] == "POP 29-SEP-2023 TO 28-SEP-2028"
    assert first["dodaac_cage"] == "N40192"
    assert first["ship_to"].startswith("COMMANDING OFFICER - NAVFAC\nMARIANAS")
    assert [r["values"]["clin"] for r in table["records"]] == ["0001", "0002", "0003", "0004"]


@_requires(NAVY)
def test_navy_clauses_reference_and_full_text(navy):
    counts = _counts(navy)
    assert counts[("FAR", BY_REFERENCE)] + counts[("DFARS", BY_REFERENCE)] == 172
    assert counts[("FAR", IN_FULL_TEXT)] + counts[("DFARS", IN_FULL_TEXT)] == 11
    clauses = _clauses(navy)
    first = clauses["52.202-1"][0]
    assert (first["title"], first["date"], first["incorporation_type"], first["regulation"]) == (
        "Definitions", "JUN 2020", BY_REFERENCE, "FAR",
    )
    for number, title, date in (
        ("52.211-10", "COMMENCEMENT, PROSECUTION, AND COMPLETION OF WORK", "APR 1984"),
        ("52.211-12", "LIQUIDATED DAMAGES--CONSTRUCTION", "SEP 2000"),
    ):
        (clause,) = clauses[number]
        assert (clause["title"], clause["date"], clause["incorporation_type"], clause["page"]) == (title, date, IN_FULL_TEXT, 12)
        assert clause["source_heading"] == "CLAUSES INCORPORATED BY FULL TEXT"
        assert "(End of clause)" in clause["text"]
    assert clauses["52.211-10"][0]["text"].startswith("The Contractor shall be required to (a) commence work")
    # A wrapped title stays with its own clause.
    assert clauses["52.203-8"][0]["title"].endswith("Illegal or Improper Activity")
    # The clause cited in narrative on page 23 is not a second record.
    assert len(clauses["52.211-10"]) == 1


# --- 47QRCA25DSF07 (GSA SF33 + continuation sheets) ---------------------------------


@pytest.fixture(scope="module")
def gsa() -> dict:
    return _structure(GSA)


@_requires(GSA)
def test_gsa_sf33_fields(gsa):
    fields = _fields(gsa)
    expected = {
        "contract.contract_number": ("2. CONTRACT NUMBER", "47QRCA25DSF07"),
        "contract.solicitation_number": ("3. SOLICITATION NUMBER", "47QRCA23R0001"),
        "contract.solicitation_type": ("4. TYPE OF SOLICITATION", "Negotiated (RFP)"),
        "contract.date_issued": ("5. DATE ISSUED", "02/03/2025"),
        "contract.requisition_number": ("6. REQUISITION/PURCHASE NUMBER", "PR-24-0000408"),
        "contract.page_of_pages": ("PAGE OF PAGES", "1 of 91"),
        "contract.issued_by_code": ("7. ISSUED BY — CODE", "47QRCA"),
        "contract.information_contact_email": ("10. FOR INFORMATION CALL — C. E-MAIL ADDRESS", "gabrina.daniels@gsa.gov"),
        "contract.award_amount": ("20. AMOUNT", "$2,500.00"),
        "contract.contracting_officer": ("26. NAME OF CONTRACTING OFFICER", "Esther Shannon"),
        "contract.award_date": ("28. AWARD DATE", "04/15/2025"),
    }
    for field_id, (label, value) in expected.items():
        assert (fields[field_id]["label"], fields[field_id]["value"]) == (label, value), field_id
    assert fields["contract.offeror"]["value"].startswith("CHUGACH BATTELLE APPLIED SOLUTIONS JV LLC")
    assert fields["contract.uei"]["value"] == "LLKXZRFEQMR3"


@_requires(GSA)
def test_gsa_continuation_sheet_line_items(gsa):
    table = gsa["tables"]["line_items"]
    # The continuation sheet says QUANTITY / AMOUNT — not MAX QUANTITY.
    assert [c["header"] for c in table["columns"]] == ["ITEM NO.", "SUPPLIES/SERVICES", "QUANTITY", "UNIT", "UNIT PRICE", "AMOUNT"]
    first = table["records"][0]["values"]
    assert (first["item_number"], first["description"], first["amount"]) == ("00001", "Funding Line", "2,500.00")
    numbers = [r["values"]["item_number"] for r in table["records"]]
    assert len(numbers) == len(set(numbers))
    assert all(n.isdigit() and len(n) == 5 for n in numbers)  # no address or NAICS lines as items


@_requires(GSA)
def test_gsa_clauses(gsa):
    counts = _counts(gsa)
    assert counts[("FAR", BY_REFERENCE)] == 109 and counts[("GSAM/R", BY_REFERENCE)] == 9
    assert counts[("FAR", IN_FULL_TEXT)] == 10 and counts[("GSAM/R", IN_FULL_TEXT)] == 3
    clauses = _clauses(gsa)
    alternates = {c["alternate"] for c in clauses["52.203-6"]}
    assert alternates == {None, "Alternate I (NOV 2021)"}
    (safeguarding,) = clauses["52.204-21"]
    assert safeguarding["incorporation_type"] == IN_FULL_TEXT and safeguarding["date"] == "NOV 2021"
    assert safeguarding["text"].startswith("As prescribed in 4.1903")


# --- FA300224C0008 (Air Force SF33) ------------------------------------------------


@pytest.fixture(scope="module")
def air_force() -> dict:
    return _structure(AIR_FORCE)


@_requires(AIR_FORCE)
def test_air_force_sf33_fields(air_force):
    fields = _fields(air_force)
    for field_id, value in {
        "contract.contract_number": "FA300224C0008",
        "contract.solicitation_number": "FA300223R00090009",
        "contract.date_issued": "21 Apr 2023",
        "contract.requisition_number": "F2X3C34150A001",
        "contract.page_of_pages": "1 of 288",
        "contract.offer_due_time": "12:00 PM",
        "contract.offer_due_date": "12 Feb 2024",
        "contract.award_amount": "USD 24,131,140.28",
        "contract.naics": "561210",
    }.items():
        assert fields[field_id]["value"] == value, field_id
    # No X is printed in its Type of Solicitation box: nothing is invented.
    assert "contract.solicitation_type" not in fields


@_requires(AIR_FORCE)
def test_air_force_schedule_without_repeated_headers(air_force):
    table = air_force["tables"]["line_items"]
    assert [c["header"] for c in table["columns"]] == ["Item", "Supplies/Service", "Quantity", "Unit", "Unit Price", "Amount"]
    records = table["records"]
    pages = {r["page"] for r in records}
    assert min(pages) == 3 and max(pages) == 80  # header printed once, table runs to Section C
    first = records[0]["values"]
    assert (first["item_number"], first["quantity"], first["unit"], first["unit_price"], first["amount"]) == (
        "0001", "10", "Months", "USD 142,035.17", "USD 1,420,351.70",
    )
    numbers = [r["values"]["item_number"] for r in records]
    assert len(numbers) == len(set(numbers)) == 421


@_requires(AIR_FORCE)
def test_air_force_far_and_dfars_clause_context(air_force):
    counts = _counts(air_force)
    assert counts[("FAR", BY_REFERENCE)] == 100 and counts[("DFARS", BY_REFERENCE)] == 60
    assert counts[("FAR", IN_FULL_TEXT)] == 24
    assert counts[("DFARS", IN_FULL_TEXT)] == 9 and counts[("AFFARS", IN_FULL_TEXT)] == 7
    clauses = _clauses(air_force)
    wawf = clauses["252.232-7006"][0]
    assert wawf["incorporation_type"] == IN_FULL_TEXT and wawf["source_heading"] == "DFARS Clauses Incorporated by Full Text"
    deviation = clauses["52.219-8"][0]
    assert deviation["title"] == "Utilization of Small Business Concerns" and deviation["date"] == "Dec 2022"
    assert "2023-O0002" in deviation["alternate"]


# --- synthetic layouts (always run) ------------------------------------------------


def _line(text: str, y: float, x: float = 60.0) -> LogicalLine:
    return LogicalLine(1, 0, 0, text, x, y, x + 6 * len(text), y + 9, "native", "native_dict_span")


def _page(rows: list[list[tuple[str, float]]], page_number: int = 1, start: float = 100.0) -> PageLines:
    """rows: each row is [(phrase, x0), ...] at increasing y."""
    lines: list[LogicalLine] = []
    words: list[Word] = []
    y = start
    for row in rows:
        for phrase, x in row:
            lines.append(_line(phrase, y, x))
            cursor = x
            for token in phrase.split():
                words.append(Word(token, cursor, y, cursor + 5 * len(token), y + 9))
                cursor += 5 * len(token) + 3
        y += 14
    return PageLines(page_number, 612, 792, tuple(lines), (), (), tuple(words))


@pytest.mark.parametrize(
    ("heading", "incorporation", "hint"),
    [
        ("CLAUSES INCORPORATED BY REFERENCE", BY_REFERENCE, None),
        ("CLAUSES INCORPORATED BY FULL TEXT", IN_FULL_TEXT, None),
        ("FAR Clauses Incorporated by Full Text", IN_FULL_TEXT, "FAR"),
        ("DFARS CLAUSES INCORPORATED BY REFERENCE", BY_REFERENCE, "DFARS"),
        ("DFARS Clauses Incorporated by Full Text", IN_FULL_TEXT, "DFARS"),
        ("I.2.4 FAR and GSAM/R Clauses in Full Text", IN_FULL_TEXT, "GSAM/R"),
        ("I.2.1 FAR 52.252-2 Clauses Incorporated by Reference (Feb 1998)", BY_REFERENCE, "FAR"),
    ],
)
def test_incorporation_headings(heading, incorporation, hint):
    context = incorporation_heading(heading)
    assert context is not None and context.incorporation == incorporation
    assert context.hint == hint


@pytest.mark.parametrize(
    "text",
    [
        "52.252-2  CLAUSES INCORPORATED BY REFERENCE (FEB 1998)",  # the clause's own heading
        "full text. Upon request, the Contracting Officer will make their full text available.",
        "I.2.4 FAR and GSAM/R Clauses in Full Text ...................................78",  # contents page
    ],
)
def test_not_incorporation_headings(text):
    assert incorporation_heading(text) is None


def test_heading_context_carries_to_the_clauses_below_it():
    page = _page(
        [
            [("CLAUSES INCORPORATED BY REFERENCE", 60)],
            [("52.202-1", 60), ("Definitions", 150), ("JUN 2020", 420)],
            [("252.203-7000", 60), ("Requirements Relating to Compensation", 150), ("SEP 2022", 420)],
            [("CLAUSES INCORPORATED BY FULL TEXT", 60)],
            [("52.211-10  COMMENCEMENT, PROSECUTION, AND COMPLETION OF WORK (APR 1984)", 60)],
            [("The Contractor shall be required to commence work.", 60)],
            [("(End of clause)", 60)],
            [("Section 00 73 00 - Supplementary Conditions", 60)],
            [("as stated in FAR Clause 52.211-10 Commencement, Prosecution", 60)],
        ]
    )
    records = read_clauses([page])
    assert [(r.clause_number, r.incorporation_type, r.regulation) for r in records] == [
        ("52.202-1", BY_REFERENCE, "FAR"),
        ("252.203-7000", BY_REFERENCE, "DFARS"),
        ("52.211-10", IN_FULL_TEXT, "FAR"),
    ]
    assert records[0].date == "JUN 2020"
    full = records[2]
    assert full.title == "COMMENCEMENT, PROSECUTION, AND COMPLETION OF WORK" and full.date == "APR 1984"
    assert full.text == "The Contractor shall be required to commence work.\n(End of clause)"


def test_stacked_max_quantity_header_is_preserved():
    page = _page(
        [
            [("ITEM NO", 46), ("SUPPLIES/SERVICES", 101), ("MAX", 228), ("UNIT", 291), ("UNIT PRICE", 355), ("MAX AMOUNT", 500)],
            [("QUANTITY", 214)],
            [("0001", 46), ("Base Period", 101), ("10", 230), ("Each", 293), ("$1.00", 371), ("$10.00", 505)],
        ]
    )
    (table,) = read_schedule_tables([page])
    assert [c.header for c in table.columns] == ["ITEM NO", "SUPPLIES/SERVICES", "MAX QUANTITY", "UNIT", "UNIT PRICE", "MAX AMOUNT"]
    assert [c.key for c in table.columns] == ["item_number", "description", "quantity", "unit", "unit_price", "amount"]
    assert table.records[0].values == {
        "item_number": "0001", "description": "Base Period", "quantity": "10", "unit": "Each",
        "unit_price": "$1.00", "amount": "$10.00",
    }


# --- staging workbook end to end (N4019223D2803) ---------------------------------------


@_requires(NAVY)
def test_navy_contract_staging_workbook():
    pdf = fitz.open(NAVY)
    pdf.set_metadata({"subject": str(uuid4())})  # the test DB dedupes uploads
    upload = client.post("/api/documents/upload", files={"file": (NAVY.name, pdf.tobytes(), "application/pdf")})
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]
    assert client.post(f"/api/documents/{document_id}/extract-pages", json={"run_ocr": False}).status_code == 200
    database = SessionLocal()
    try:
        document = database.get(Document, document_id)
        rows = list(database.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id)))
        run_and_persist_v3_extraction(database=database, document=document, pages=rows)
        resolve_and_persist_profile(database, document)
    finally:
        database.close()

    workbook = client.get(f"/api/documents/{document_id}/staging-workbook").json()
    datasets = {d["dataset_id"]: d for d in workbook["datasets"]}

    details = datasets["contract_details"]
    by_id = {r["cells"]["contract.detail.field_id"]["value"]: r["cells"] for r in details["records"]}
    solicitation = by_id["contract.solicitation_number"]
    assert solicitation["contract.detail.label"]["value"] == "1. SOLICITATION NO."
    assert solicitation["contract.detail.value"]["value"] == "N4019221R28000019"
    assert solicitation["contract.detail.value"]["review_status"] == "Verified"
    assert solicitation["contract.detail.value"]["provenance"]["source_page"] == 1
    assert all(r["record_status"] == "Verified" for r in details["records"])

    lines = datasets["line_items"]
    assert [c["display_label"] for c in lines["columns"]][:3] == ["ITEM NO", "SUPPLIES/SERVICES", "MAX QUANTITY"]
    assert len(lines["records"]) == 4

    clauses = datasets["contract_clauses"]
    assert clauses["compact"] is True
    assert clauses["grid_fields"] == [
        "contract.contract_clause.clause_number",
        "contract.contract_clause.title",
        "contract.contract_clause.date",
        "contract.contract_clause.incorporation_type",
    ]
    full_text = [
        r for r in clauses["records"]
        if r["cells"]["contract.contract_clause.incorporation_type"]["value"] == IN_FULL_TEXT
    ]
    assert {r["cells"]["contract.contract_clause.clause_number"]["value"] for r in full_text} >= {"52.211-10", "52.211-12"}
    record_id = next(
        r["record_id"] for r in full_text if r["cells"]["contract.contract_clause.clause_number"]["value"] == "52.211-10"
    )
    detail = client.get(f"/api/documents/{document_id}/staging-workbook/datasets/contract_clauses/records/{record_id}")
    assert detail.status_code == 200, detail.text
    text = detail.json()["cells"]["contract.contract_clause.text"]["value"]
    assert text.startswith("The Contractor shall be required to") and text.rstrip().endswith("(End of clause)")

    transform = datasets["clause_transformation"]
    row = next(r for r in transform["records"] if r["cells"]["contract.clause_transform.number"]["value"] == "52.211-10")
    assert row["cells"]["contract.clause_transform.insert_by_reference"]["value"] == "N"
    assert row["cells"]["contract.clause_transform.display_name"]["value"].startswith("52.211-10 COMMENCEMENT")
    assert row["cells"]["contract.clause_transform.action"]["value"] is None  # no approved rule: not invented

    # V3 is untouched: its summary keeps exactly its 14 columns.
    assert len(datasets["contract_summary"]["columns"]) == 14
