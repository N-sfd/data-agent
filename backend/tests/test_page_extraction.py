from pathlib import Path

import fitz

from app.core.config import get_settings
from app.services.ocr_detection import (
    detect_ocr_requirement,
)
from app.services.page_text_extractor import extract_page


settings = get_settings()


def create_digital_pdf(file_path: Path) -> None:
    pdf = fitz.open()
    page = pdf.new_page()

    page.insert_text(
        (72, 72),
        (
            "FY2025 Financial Report\n"
            "Operating expenses were $12,500,000.\n"
            "Revenue was $42,000,000."
        ),
    )

    pdf.save(file_path)
    pdf.close()


def create_image_only_pdf(file_path: Path) -> None:
    image_document = fitz.open()
    image_page = image_document.new_page()

    image_page.draw_rect(
        fitz.Rect(40, 40, 550, 740),
        fill=(0.95, 0.95, 0.95),
    )

    pixmap = image_page.get_pixmap(dpi=150)

    image_document.close()

    pdf = fitz.open()
    page = pdf.new_page()

    page.insert_image(
        page.rect,
        stream=pixmap.tobytes("png"),
    )

    pdf.save(file_path)
    pdf.close()


def test_extract_native_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "digital.pdf"
    create_digital_pdf(pdf_path)

    pdf = fitz.open(pdf_path)

    result = extract_page(
        document=pdf,
        page_index=0,
        settings=settings,
        run_ocr=False,
    )

    pdf.close()

    assert result.page_number == 1
    assert "Operating expenses" in result.final_text
    assert result.extraction_method == "native"
    assert result.detection.requires_ocr is False


def test_detect_image_only_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    create_image_only_pdf(pdf_path)

    pdf = fitz.open(pdf_path)
    page = pdf[0]

    native_text = page.get_text("text")
    blocks = page.get_text("blocks")

    detection = detect_ocr_requirement(
        page=page,
        native_text=native_text,
        native_blocks=blocks,
        settings=settings,
    )

    pdf.close()

    assert detection.requires_ocr is True
    assert detection.image_count >= 1


def test_page_number_preserved(tmp_path: Path) -> None:
    pdf_path = tmp_path / "multi-page.pdf"

    pdf = fitz.open()

    for page_number in range(1, 4):
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            f"Financial report page {page_number}",
        )

    pdf.save(pdf_path)
    pdf.close()

    pdf = fitz.open(pdf_path)

    result = extract_page(
        document=pdf,
        page_index=1,
        settings=settings,
        run_ocr=False,
    )

    pdf.close()

    assert result.page_number == 2
    assert "page 2" in result.final_text
