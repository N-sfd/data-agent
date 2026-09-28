"""Every processed document resolves to an explicit outcome — never a blank
Results workbook (app/services/extraction_outcome.py,
app/services/source_inspection.py)."""

import fitz

from app.schemas.v3_document import (
    AllFieldsRow,
    ContractSummaryRow,
    NormalizedV3Document,
)
from app.services.extraction_outcome import build_extraction_outcome
from app.services.source_inspection import (
    SOURCE_KIND_PDF_EMBEDDED_FILES,
    SOURCE_KIND_PDF_PORTFOLIO,
    SOURCE_KIND_STANDARD,
    inspect_pdf,
)


def _doc(**overrides) -> NormalizedV3Document:
    fields = dict(
        document_id="doc-1",
        document_filename="Contract.pdf",
        all_fields=[],
        clins=[],
        funding=[],
        performance_delivery=[],
        attachments=[],
        clauses=[],
        far_references=[],
        dfars=[],
        source_documents=[],
        qa_review=[],
        contract_summary=None,
    )
    fields.update(overrides)
    return NormalizedV3Document(**fields)


def _field(qa_status: str) -> AllFieldsRow:
    return AllFieldsRow(
        category="General",
        normalized_field="Contract Number",
        value="47QRCA25DSF07",
        source_file="Contract.pdf",
        source_page=2,
        evidence="47QRCA25DSF07",
        extraction_method="deterministic",
        qa_status=qa_status,
    )


def _completed(inspection: dict | None = None) -> dict:
    return {"v3_extraction": {"status": "completed", "error": None, "source_inspection": inspection}}


def _pdf(*, embedded: bool = False, portfolio: bool = False) -> fitz.Document:
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), "Placeholder")
    if embedded:
        pdf.embfile_add("SF1442 Award.pdf", b"%PDF-1.4 stub", filename="SF1442 Award.pdf")
    if portfolio:
        pdf.xref_set_key(pdf.pdf_catalog(), "Collection", "<< /Type /Collection >>")
    return fitz.open("pdf", pdf.tobytes())


# --- outcome ---


def test_verified_records_are_populated():
    outcome = build_extraction_outcome(_doc(all_fields=[_field("Verified")]), _completed())
    assert outcome.status == "populated"
    assert outcome.record_count == 1


def test_any_needs_review_record_makes_outcome_needs_review():
    doc = _doc(
        all_fields=[_field("Verified")],
        contract_summary=ContractSummaryRow(contract_number="X", qa_status="Needs Review"),
    )
    outcome = build_extraction_outcome(doc, _completed())
    assert outcome.status == "needs_review"
    assert outcome.record_count == 2
    assert outcome.needs_review_count == 1


def test_clean_run_with_no_records_is_explicit_not_blank():
    outcome = build_extraction_outcome(_doc(), _completed({"kind": SOURCE_KIND_STANDARD}))
    assert outcome.status == "no_supported_fields"
    assert outcome.message


def test_no_recorded_run_and_no_records_is_pending():
    assert build_extraction_outcome(_doc(), {}).status == "pending"
    assert build_extraction_outcome(_doc(), None).status == "pending"


def test_records_without_a_recorded_run_still_show_as_results():
    # Documents extracted before outcomes were recorded must not regress
    # to "pending" when they already have data.
    outcome = build_extraction_outcome(_doc(all_fields=[_field("Verified")]), {})
    assert outcome.status == "populated"


def test_failed_stage_is_reported_as_failed():
    provenance = {"v3_extraction": {"status": "failed", "error": "KeyError"}}
    outcome = build_extraction_outcome(_doc(), provenance)
    assert outcome.status == "failed"
    assert outcome.details == ["Error type: KeyError"]


def test_portfolio_is_special_source_listing_embedded_files():
    inspection = {
        "kind": SOURCE_KIND_PDF_PORTFOLIO,
        "embedded_files": [{"name": "SF1442 Award.pdf", "size_bytes": 10}],
    }
    outcome = build_extraction_outcome(_doc(), _completed(inspection))
    assert outcome.status == "special_source"
    assert outcome.details == ["SF1442 Award.pdf"]


def test_ordinary_pdf_attachments_are_noted_alongside_results():
    inspection = {
        "kind": SOURCE_KIND_PDF_EMBEDDED_FILES,
        "embedded_files": [{"name": "Pricing.xlsx", "size_bytes": 10}],
    }
    outcome = build_extraction_outcome(_doc(all_fields=[_field("Verified")]), _completed(inspection))
    assert outcome.status == "populated"
    assert outcome.details == ["Embedded file: Pricing.xlsx"]


# --- source inspection ---


def test_inspect_standard_pdf():
    assert inspect_pdf(_pdf()).kind == SOURCE_KIND_STANDARD


def test_inspect_pdf_with_attachment_is_not_a_portfolio():
    result = inspect_pdf(_pdf(embedded=True))
    assert result.kind == SOURCE_KIND_PDF_EMBEDDED_FILES
    assert [item.name for item in result.embedded_files] == ["SF1442 Award.pdf"]


def test_inspect_portfolio_requires_collection_entry():
    result = inspect_pdf(_pdf(embedded=True, portfolio=True))
    assert result.kind == SOURCE_KIND_PDF_PORTFOLIO
    assert len(result.embedded_files) == 1


def test_portfolio_upload_lists_page_counts_for_the_picker():
    """The picker orders embedded files by page count so the main document
    (a 33-page award) isn't buried under a 2-page cover letter."""

    from uuid import uuid4

    import fitz
    from fastapi.testclient import TestClient

    from app.main import app

    def pdf(pages: int) -> bytes:
        doc = fitz.open()
        for i in range(pages):
            doc.new_page().insert_text((72, 72), f"page {i + 1} {uuid4()}")
        return doc.tobytes()

    portfolio = fitz.open()
    portfolio.new_page().insert_text(
        (72, 72), "For the best experience, open this PDF portfolio in Acrobat X or Adobe Reader X, or later."
    )
    portfolio.embfile_add("letter.pdf", pdf(2), filename="letter.pdf")
    portfolio.embfile_add("award.pdf", pdf(5), filename="award.pdf")

    response = TestClient(app).post(
        "/api/documents/upload",
        files={"file": (f"portfolio-{uuid4()}.pdf", portfolio.tobytes(), "application/pdf")},
    )
    assert response.status_code in (200, 201), response.text
    files = {f["filename"]: f["page_count"] for f in response.json()["embedded_files"]}
    assert files == {"letter.pdf": 2, "award.pdf": 5}
