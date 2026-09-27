"""Universal structure-aware source extraction (app/source_structure/):
schema-neutral label/value, table and region recovery from PDF (native and
OCR) and HTML, with provenance — no business vocabulary."""

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
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.services.v3_orchestrator import run_and_persist_v3_extraction
from app.source_structure.html_structure import extract_html_structure, readable_dom_text
from app.source_structure.ocr_geometry import OcrCoordinateSpace, coordinate_space_for
from app.source_structure.pdf_structure import extract_page_structure, native_words
from app.source_structure.text_shapes import infer_value_type, label_rejection
from app.staging.resolver import resolve_and_persist_profile

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures" / "html"


# --- label shape and value types ----------------------------------------------


@pytest.mark.parametrize(
    "label",
    ["Invoice Number", "Invoice Date", "Account Number", "Customer ID", "Ship To",
     "Payment Terms", "Total Due", "Tax ID:", "PO #", "Sales Tax (10.2%)", "• DNA"],
)
def test_noun_phrase_labels_are_accepted(label):
    assert label_rejection(label) is None


@pytest.mark.parametrize(
    "label",
    ["Contractor shall email", "Please remit payment within",
     "For additional information contact", "The supplier agrees that",
     "Questions about this invoice", "of the Government, for example"],
)
def test_clause_shaped_labels_are_rejected(label):
    assert label_rejection(label) is not None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("INV-2025-0417", "identifier"),
        ("03/14/2025", "date"),
        ("2026-08-31", "date"),
        ("09/18/2026 10:30 AM", "datetime"),
        ("$1,240.55", "currency"),
        ("12,114.05", "currency"),
        ("10.2%", "percentage"),
        ("16", "number"),
        ("billing@example.com", "email"),
        ("(253) 555-0142", "phone"),
        ("Yes", "boolean"),
        ("PO Box 4410\nOakland, CA 94607", "address"),
        ("Net 30", "text"),
    ],
)
def test_value_type_hints(value, expected):
    assert infer_value_type(value) == expected


# --- OCR coordinates ------------------------------------------------------------


def test_ocr_pixels_scale_to_pdf_points():
    space = OcrCoordinateSpace(dpi=144, image_width=1224, image_height=1584)
    assert space.to_pdf_points((144, 288, 288, 432)) == pytest.approx((72, 144, 144, 216))


def test_ocr_deskew_is_undone_about_the_image_centre():
    space = OcrCoordinateSpace(dpi=72, image_width=200, image_height=200, deskew_degrees=90)
    # A point right of centre, after a 90° CCW rotation (y down), sits above
    # it; undoing it maps back to the right.
    x0, y0, x1, y1 = space.to_pdf_points((100, 50, 100, 50))
    assert (round(x0), round(y0)) == (150, 100)


def test_legacy_layouts_infer_their_dpi():
    space = coordinate_space_for(
        {"words": [], "preprocess": ["deskew_+1.5"]},
        page_width_pt=612, page_height_pt=792, ocr_dpi=300,
    )
    assert space.dpi == 220  # capped layout DPI used by the OCR layer
    assert space.deskew_degrees == 1.5


# --- PDF structure ------------------------------------------------------------


def _pdf_page(draw) -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    draw(page)
    return fitz.open("pdf", doc.tobytes())[0]


def _structure(page):
    return extract_page_structure(
        page_number=1, words=native_words(page), extraction_method="native", fitz_page=page
    )


def _statement(page):
    def t(x, y, s, bold=False):
        page.insert_text((x, y), s, fontsize=10, fontname="hebo" if bold else "helv")

    t(40, 60, "Harbor Utilities Cooperative", bold=True)
    t(360, 90, "Account Number:", bold=True)
    t(460, 90, "ACCT-558210")
    t(360, 104, "Statement Date:", bold=True)
    t(460, 104, "08/31/2026")
    t(40, 120, "Service Address:", bold=True)
    t(40, 134, "77 Birch Lane")
    t(40, 148, "Tacoma, WA 98402")
    t(40, 200, "Meter Reading: 55120")
    cols = [40, 110, 330, 420, 510]
    for x, h in zip(cols, ["Date", "Charge", "Usage", "Rate", "Amount"]):
        t(x, 240, h, bold=True)
    rows = [
        ("08/01/2026", "Water service base fee", "1", "12.00", "12.00"),
        ("08/01/2026", "Metered consumption", "4200", "0.01", "42.00"),
        ("08/15/2026", "Stormwater surcharge", "1", "6.50", "6.50"),
    ]
    for i, row in enumerate(rows):
        for x, v in zip(cols, row):
            t(x, 258 + 18 * i, v)
    t(420, 330, "Balance Due:", bold=True)
    t(510, 330, "60.50")


def test_pdf_label_value_and_table_recovered_without_vocabulary():
    result = _structure(_pdf_page(_statement))
    fields = {f.label_text: f for f in result.fields if f.acceptance == "accepted"}

    assert fields["Account Number"].raw_value == "ACCT-558210"
    assert fields["Account Number"].structural_relation == "left_right_separator"
    assert fields["Statement Date"].value_type_hint == "date"
    assert fields["Service Address"].structural_relation == "label_above_value"
    assert fields["Service Address"].raw_value == "77 Birch Lane\nTacoma, WA 98402"
    assert fields["Meter Reading"].structural_relation == "same_line_separator"
    assert fields["Balance Due"].value_type_hint == "currency"
    # Every value carries its own geometry.
    assert all(f.value_bbox for f in fields.values())

    tables = [t for t in result.tables if t.acceptance == "accepted"]
    assert len(tables) == 1
    table = tables[0]
    assert table.headers == ["Date", "Charge", "Usage", "Rate", "Amount"]
    assert len(table.rows) == 3
    assert all(cell.bbox for row in table.rows for cell in row if cell.text)
    assert "repeating_records" in table.table_hints
    assert "numeric_amount_column" in table.column_hints[4]
    assert "date_column" in table.column_hints[0]


def test_two_column_prose_is_not_a_table():
    left = [
        "The committee reviewed the annual plan and",
        "agreed that maintenance priorities should",
        "focus on the oldest facilities first, with",
        "attention to safety and accessibility work.",
    ]
    right = [
        "Budget discussions continued into the",
        "afternoon session where members asked",
        "for clearer reporting on deferred repairs",
        "and on the status of pending contracts.",
    ]

    def draw(page):
        for i, (a, b) in enumerate(zip(left, right)):
            page.insert_text((40, 100 + 14 * i), a, fontsize=10)
            page.insert_text((320, 100 + 14 * i), b, fontsize=10)

    result = _structure(_pdf_page(draw))
    assert not [t for t in result.tables if t.acceptance == "accepted"]
    assert not [f for f in result.fields if f.acceptance == "accepted"]
    assert any(r.region_type in ("PARAGRAPH", "NARRATIVE") for r in result.regions)


def test_sentence_with_colon_is_not_a_field():
    def draw(page):
        page.insert_text((40, 100), "Please remit payment within: thirty days of receipt", fontsize=10)
        page.insert_text((40, 120), "The supplier agrees that: all goods are new", fontsize=10)

    result = _structure(_pdf_page(draw))
    assert not [f for f in result.fields if f.acceptance == "accepted"]


# --- HTML fixtures A–E ----------------------------------------------------------


def _html(name: str):
    return extract_html_structure((FIXTURES / name).read_bytes())


def test_html_a_semantic_table_stays_a_table_with_cell_locators():
    x = _html("a_semantic_table.html")
    assert not x.fields
    (table,) = x.tables
    assert table.acceptance == "accepted"
    assert table.headers == ["Line", "Part Number", "Description", "Qty", "Unit Cost", "Extended"]
    assert [c.text for c in table.rows[1]][:3] == ["2", "HX-4410", "Quick coupler, brass"]
    assert table.total_row_indices == [3]  # <tfoot>
    cell = table.rows[1][4]
    assert cell.source_locator.table_index == 0
    assert (cell.source_locator.row_index, cell.source_locator.column_index) == (1, 4)
    assert cell.source_locator.dom_path.endswith("tbody/tr[2]/td[5]")
    assert cell.source_locator.section_path == ["Shipment Manifest"]


def test_html_b_div_layouts_keep_labels_with_values():
    x = _html("b_div_label_value.html")
    pairs = {f.label_text: (f.raw_value, f.structural_relation) for f in x.fields if f.acceptance == "accepted"}
    assert pairs["Account Number"] == ("ACCT-558210", "html_adjacent_elements")
    assert pairs["Balance Due"][0] == "$1,240.55"
    assert pairs["Payment Terms"] == ("Net 15", "html_label_for")
    assert pairs["Customer ID"] == ("C-10442", "html_inline_separator")
    assert pairs["Contact Email"][0] == "ar@example.com"
    # The instruction sentence is narrative, not a field.
    assert not any("remit" in label.lower() for label in pairs)
    terms = next(f for f in x.fields if f.label_text == "Payment Terms")
    assert terms.source_locator.element_id == "terms"


def test_html_c_definition_list_pairs_dt_with_dd():
    x = _html("c_definition_list.html")
    pairs = {f.label_text: f for f in x.fields}
    assert set(pairs) == {"Vendor Name", "Tax ID", "Remit Address", "Phone", "Preferred Currency"}
    assert pairs["Remit Address"].raw_value == "PO Box 4410\nOakland, CA 94607"
    assert pairs["Phone"].value_type_hint == "phone"
    assert all(f.structural_relation == "html_definition_list" for f in pairs.values())


def test_html_d_nested_sections_give_section_trails():
    x = _html("d_nested_sections.html")
    by_label = {f.label_text: f for f in x.fields}
    assert by_label["Department"].source_locator.section_path == ["Work Order WO-7781", "Requester"]
    assert by_label["Start Date"].source_locator.section_path == [
        "Work Order WO-7781", "Schedule", "Service Window",
    ]
    # A header-less th/td table is a key/value layout, not a data table.
    assert by_label["Room"].raw_value == "B-114"
    assert by_label["Room"].structural_relation == "html_table_header_cell"
    assert not x.tables


def test_html_e_narrative_does_not_become_fields():
    x = _html("e_narrative_with_table.html")
    assert not x.fields
    (table,) = x.tables
    assert table.headers == ["Site", "Inspection Date", "Technician", "Cost"]
    assert len(table.rows) == 3
    assert "date_column" in table.column_hints[1]
    kinds = {r.region_type for r in x.regions}
    assert "NARRATIVE" in kinds


def test_readable_dom_text_keeps_structure_and_drops_script():
    text, tables = readable_dom_text((FIXTURES / "a_semantic_table.html").read_bytes())
    assert "Line | Part Number | Description" in text
    assert "border-collapse" not in text
    assert tables and tables[0]["headers"][0] == "Line"


# --- end to end ---------------------------------------------------------------------


def _upload(name: str, content: bytes, mime: str) -> str:
    # The test DB persists across runs; make every upload unique so
    # duplicate detection doesn't intercept it.
    if mime == "text/html":
        content = content + f"<!-- {uuid4()} -->".encode()
    else:
        pdf = fitz.open("pdf", content)
        pdf.set_metadata({"subject": str(uuid4())})
        content = pdf.tobytes()
    response = client.post("/api/documents/upload", files={"file": (name, content, mime)})
    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]
    extracted = client.post(f"/api/documents/{document_id}/extract-pages", json={"run_ocr": False})
    assert extracted.status_code == 200, extracted.text
    return document_id


def _process(document_id: str) -> None:
    database = SessionLocal()
    try:
        document = database.get(Document, document_id)
        pages = list(database.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id)))
        run_and_persist_v3_extraction(database=database, document=document, pages=pages)
        resolve_and_persist_profile(database, document)
    finally:
        database.close()


def _dataset(workbook: dict, dataset_id: str) -> dict:
    return next(d for d in workbook["datasets"] if d["dataset_id"] == dataset_id)


def test_pdf_statement_populates_generic_workbook_with_cell_provenance():
    doc = fitz.open()
    _statement(doc.new_page(width=612, height=792))
    document_id = _upload(f"statement-{uuid4()}.pdf", doc.tobytes(), "application/pdf")
    _process(document_id)

    workbook = client.get(f"/api/documents/{document_id}/staging-workbook").json()
    assert workbook["profile"]["profile_id"] == "generic_business_document"
    assert workbook["profile"]["profile_version"] == 2
    keys = {r["cells"]["document.field.name"]["value"]: r for r in _dataset(workbook, "key_fields")["records"]}
    account = keys["Account Number"]["cells"]["document.field.value"]
    assert account["value"] == "ACCT-558210"
    assert account["review_status"] == "Verified"
    assert account["provenance"]["source_page"] == 1
    assert account["provenance"]["source_bbox"] is not None

    lines = _dataset(workbook, "line_items")["records"]
    assert len(lines) == 3
    amount = lines[1]["cells"]["document.line_item.amount"]
    assert amount["value"] == "42.00"
    assert amount["provenance"]["highlight_text"] == "42.00"
    assert amount["provenance"]["source_bbox"] is not None


def test_html_document_uses_dom_provenance_without_page_numbers():
    html = (FIXTURES / "a_semantic_table.html").read_bytes()
    document_id = _upload(f"manifest-{uuid4()}.html", html, "text/html")
    _process(document_id)

    workbook = client.get(f"/api/documents/{document_id}/staging-workbook").json()
    assert workbook["outcome"]["status"] in ("populated", "needs_review")
    lines = _dataset(workbook, "line_items")["records"]
    assert len(lines) == 3
    cell = lines[0]["cells"]["document.line_item.description"]
    provenance = cell["provenance"]
    assert provenance["source_type"] == "html"
    assert provenance["source_page"] is None
    assert provenance["source_locator"]["table_index"] == 0
    assert provenance["source_locator"]["column_index"] == 2

    context = client.get(
        f"/api/documents/{document_id}/source-structure/regions/{provenance['source_region_id']}"
    ).json()
    assert context["table"]["headers"][2] == "Description"
    assert (context["row_index"], context["column_index"]) == (0, 2)

    # The tfoot total surfaces as a key field from the table's total row.
    keys = {r["cells"]["document.field.name"]["value"] for r in _dataset(workbook, "key_fields")["records"]}
    assert "Total" in keys


def test_document_pinned_to_generic_v1_keeps_rendering_v1():
    document_id = _upload(f"memo-{uuid4()}.pdf", _one_line_pdf(), "application/pdf")
    database = SessionLocal()
    try:
        database.add(
            DocumentStagingWorkbook(
                document_id=document_id,
                profile_id="generic_business_document",
                profile_version=1,
                resolution_reasons=["pinned before phase C"],
            )
        )
        database.commit()
    finally:
        database.close()
    workbook = client.get(f"/api/documents/{document_id}/staging-workbook").json()
    assert workbook["profile"]["profile_version"] == 1


def _one_line_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Internal memo", fontsize=10)
    return doc.tobytes()
