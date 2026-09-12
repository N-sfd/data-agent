"""OCR helper for images embedded inside Office containers."""

from __future__ import annotations

import time
from io import BytesIO

from app.core.observability import log_event


def ocr_image_bytes(
    image_bytes: bytes,
    *,
    language: str = "eng",
    timeout_seconds: int = 45,
    page_number: int | None = None,
) -> str:
    """Best-effort, time-bounded OCR of an embedded raster.

    Returns an empty string on failure or timeout rather than raising —
    callers treat "no text recovered" as a normal outcome.
    """

    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return ""

    started = time.perf_counter()

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            rgb = image.convert("RGB")
            text = (
                pytesseract.image_to_string(
                    rgb, lang=language, timeout=timeout_seconds
                )
                or ""
            ).strip()

        log_event(
            "embedded_image_ocr",
            stage="rendering_ocr",
            status="complete",
            ocr_engine="tesseract",
            page=page_number,
            duration_ms=int((time.perf_counter() - started) * 1000),
            text_chars=len(text),
        )
        return text
    except RuntimeError as exc:
        # pytesseract raises a bare RuntimeError for its own timeout.
        log_event(
            "embedded_image_ocr",
            stage="rendering_ocr",
            status="timeout",
            error_category=type(exc).__name__,
            ocr_engine="tesseract",
            page=page_number,
            duration_ms=int((time.perf_counter() - started) * 1000),
            timeout_seconds=timeout_seconds,
        )
        return ""
    except Exception as exc:
        log_event(
            "embedded_image_ocr",
            stage="rendering_ocr",
            status="error",
            error_category=type(exc).__name__,
            ocr_engine="tesseract",
            page=page_number,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return ""
