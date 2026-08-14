import io

import fitz
import pytesseract
from PIL import Image

OCR_TEXT_THRESHOLD = 30
RENDER_SCALE = 2


def _ocr_page(page: fitz.Page) -> tuple[str, float]:
    """Render a PDF page to an image and run OCR. Returns (text, confidence)."""
    pixmap = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE))
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    confidences: list[float] = []
    for conf in data["conf"]:
        try:
            value = float(conf)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            confidences.append(value)

    text = pytesseract.image_to_string(image).strip()
    confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return text, confidence


def parse_pdf(file_path: str) -> list[dict]:
    pages = []
    pdf = fitz.open(file_path)

    for page_number, page in enumerate(pdf, start=1):
        text = page.get_text("text").strip()
        requires_ocr = len(text) < OCR_TEXT_THRESHOLD

        page_result = {
            "page_number": page_number,
            "text": text,
            "requires_ocr": requires_ocr,
            "ocr_used": False,
            "ocr_confidence": None,
        }

        if requires_ocr:
            ocr_text, ocr_confidence = _ocr_page(page)
            page_result["text"] = ocr_text
            page_result["ocr_used"] = True
            page_result["ocr_confidence"] = ocr_confidence

        pages.append(page_result)

    return pages
