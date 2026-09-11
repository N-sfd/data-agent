"""OCR helper for images embedded inside Office containers."""

from __future__ import annotations

from io import BytesIO


def ocr_image_bytes(image_bytes: bytes, *, language: str = "eng") -> str:
    """Best-effort OCR of an embedded raster. Empty string on failure."""

    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return ""

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            rgb = image.convert("RGB")
            text = pytesseract.image_to_string(rgb, lang=language) or ""
            return text.strip()
    except Exception:
        return ""
