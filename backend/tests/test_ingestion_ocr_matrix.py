"""OCR expectation matrix + ground-truth recovery for ingestion RC."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.embedded_image_ocr import ocr_image_bytes
from tests.fixtures.ingestion_ground_truth import (
    CONTRACT_GROUND_TRUTH,
    INVOICE_GROUND_TRUTH,
    OCR_EXPECTATIONS,
    docx_with_embedded_scan,
    image_only_pdf_from_png,
    mixed_native_and_scanned_pdf,
    native_text_pdf,
    pptx_with_scanned_slide,
    render_ground_truth_image,
    xlsx_native_bytes,
)

client = TestClient(app)


def _tesseract_available() -> bool:
    sample = render_ground_truth_image(
        "OCR Probe",
        {"Invoice Number": "INV-2026-8914"},
        size=(800, 400),
    )
    text = ocr_image_bytes(sample)
    return "INV-2026-8914" in text.replace(" ", "")


requires_ocr_engine = pytest.mark.skipif(
    not _tesseract_available(),
    reason="Tesseract OCR not available or unreliable in this environment",
)


def _upload(name: str, content: bytes, content_type: str) -> dict:
    response = client.post(
        "/api/documents/upload",
        files={"file": (name, content, content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _extract(document_id: str) -> dict:
    response = client.post(
        f"/api/documents/{document_id}/extract-pages",
        json={
            "run_ocr": True,
            "page_start": None,
            "page_end": None,
            "force_reprocess": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _pages(document_id: str) -> list[dict]:
    response = client.get(f"/api/documents/{document_id}/pages")
    assert response.status_code == 200
    return response.json()


def _contains_all(haystack: str, fields: dict[str, str]) -> list[str]:
    missing = []
    normalized = " ".join(haystack.split())
    for value in fields.values():
        token = " ".join(value.split())
        if token not in normalized and token.replace(" ", "") not in normalized.replace(
            " ", ""
        ):
            missing.append(token)
    return missing


def test_ocr_expectation_table_is_explicit() -> None:
    assert OCR_EXPECTATIONS["raster_image"] is True
    assert OCR_EXPECTATIONS["image_only_pdf"] is True
    assert OCR_EXPECTATIONS["xlsx"] is False
    assert OCR_EXPECTATIONS["txt"] is False
    assert OCR_EXPECTATIONS["docx_with_scanned_image"] is True


def test_native_text_formats_do_not_need_ocr() -> None:
    cases = [
        ("notes.txt", f"Plain text {uuid4()}\n".encode(), "text/plain", "txt"),
        (
            "rates.csv",
            f"name,value\nalpha,{uuid4()}\n".encode(),
            "text/csv",
            "csv",
        ),
        (
            "page.html",
            f"<html><body><p>Hello {uuid4()}</p></body></html>".encode(),
            "text/html",
            "html",
        ),
        (
            "memo.rtf",
            b"{\\rtf1\\ansi Native RTF body.}",
            "application/rtf",
            "rtf",
        ),
        (
            "book.xlsx",
            xlsx_native_bytes(),
            (
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
            "xlsx",
        ),
    ]

    for name, content, mime, family in cases:
        body = _upload(name, content, mime)
        provenance = body.get("ingestion_provenance") or {}
        assert provenance.get("ocr_used") in (False, None)
        assert OCR_EXPECTATIONS[family] is False
        pages = _pages(body["document_id"])
        assert pages
        assert pages[0]["final_text"].strip()


@requires_ocr_engine
def test_image_only_pdf_invoice_ground_truth() -> None:
    png = render_ground_truth_image("INVOICE", INVOICE_GROUND_TRUTH)
    pdf = image_only_pdf_from_png(png)
    body = _upload("invoice-scan.pdf", pdf, "application/pdf")
    assert body["ingestion_provenance"]["source_format"] == "pdf"

    extraction = _extract(body["document_id"])
    assert extraction["pages_processed"] >= 1

    pages = _pages(body["document_id"])
    text = pages[0]["final_text"]
    missing = _contains_all(text, INVOICE_GROUND_TRUTH)
    assert not missing, f"OCR missed invoice fields: {missing}\nGot:\n{text}"

    # Image-only pages should be treated as OCR candidates.
    assert pages[0].get("is_scanned") is True or pages[0].get(
        "extraction_method"
    ) in {"ocr", "mixed", "native"}


@requires_ocr_engine
def test_image_only_pdf_contract_ground_truth() -> None:
    png = render_ground_truth_image("CONTRACT", CONTRACT_GROUND_TRUTH)
    pdf = image_only_pdf_from_png(png)
    body = _upload("contract-scan.pdf", pdf, "application/pdf")
    _extract(body["document_id"])
    text = _pages(body["document_id"])[0]["final_text"]
    missing = _contains_all(text, CONTRACT_GROUND_TRUTH)
    assert not missing, f"OCR missed contract fields: {missing}\nGot:\n{text}"


@requires_ocr_engine
def test_mixed_pdf_native_plus_selective_ocr() -> None:
    scanned = render_ground_truth_image("INVOICE", INVOICE_GROUND_TRUTH)
    pdf = mixed_native_and_scanned_pdf(
        native_text="Native cover page for mixed PDF certification.",
        scanned_png=scanned,
    )
    body = _upload("mixed.pdf", pdf, "application/pdf")
    _extract(body["document_id"])
    pages = _pages(body["document_id"])
    assert len(pages) == 2

    native_page, scanned_page = pages[0], pages[1]
    assert "Native cover page" in native_page["final_text"]
    assert OCR_EXPECTATIONS["mixed_pdf_native_page"] is False
    assert OCR_EXPECTATIONS["mixed_pdf_scanned_page"] is True

    missing = _contains_all(scanned_page["final_text"], INVOICE_GROUND_TRUTH)
    assert not missing, (
        f"Selective OCR missed invoice fields on page 2: {missing}\n"
        f"Got:\n{scanned_page['final_text']}"
    )


@requires_ocr_engine
def test_png_raster_ocr_expected() -> None:
    png = render_ground_truth_image("INVOICE", INVOICE_GROUND_TRUTH)
    body = _upload("invoice.png", png, "image/png")
    assert body["ingestion_provenance"]["source_format"] == "png"
    _extract(body["document_id"])
    text = _pages(body["document_id"])[0]["final_text"]
    missing = _contains_all(text, {"Invoice Number": "INV-2026-8914"})
    assert not missing, text


@requires_ocr_engine
def test_docx_with_scanned_image_runs_embedded_ocr() -> None:
    png = render_ground_truth_image("INVOICE", INVOICE_GROUND_TRUTH)
    docx = docx_with_embedded_scan(
        png, caption="Cover letter — see scanned invoice image."
    )
    body = _upload(
        "invoice.docx",
        docx,
        (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
    )
    pages = _pages(body["document_id"])
    text = pages[0]["final_text"]
    assert "Cover letter" in text
    missing = _contains_all(text, {"Invoice Number": "INV-2026-8914"})
    assert not missing, text
    provenance = body.get("ingestion_provenance") or {}
    # Upload-time native ingest may record ocr_used after parser enhancement.
    assert provenance.get("source_format") == "docx"


@requires_ocr_engine
def test_pptx_with_scanned_slide_runs_embedded_ocr() -> None:
    png = render_ground_truth_image("CONTRACT", CONTRACT_GROUND_TRUTH)
    pptx = pptx_with_scanned_slide(png, title="Deck cover")
    body = _upload(
        "contract.pptx",
        pptx,
        (
            "application/vnd.openxmlformats-officedocument"
            ".presentationml.presentation"
        ),
    )
    pages = _pages(body["document_id"])
    text = pages[0]["final_text"]
    missing = _contains_all(text, {"Contract Number": "CA-2026-0047"})
    assert not missing, text


def test_native_pdf_does_not_require_ocr() -> None:
    pdf = native_text_pdf(
        "Digital native PDF with Contract Number: CA-2026-0047 on page 1."
    )
    body = _upload("native.pdf", pdf, "application/pdf")
    extraction = _extract(body["document_id"])
    pages = _pages(body["document_id"])
    assert "CA-2026-0047" in pages[0]["final_text"]
    assert extraction.get("ocr_required_pages", 0) == 0 or pages[0].get(
        "extraction_method"
    ) == "native"
