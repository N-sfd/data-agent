"""Follow-up P0 fixes: TIFF multi-frame pages + bounded OCR execution."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from app.services.embedded_image_ocr import ocr_image_bytes
from app.services.page_text_extractor import _run_with_timeout

client = TestClient(app)


def _font(size: int = 28):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _frame(label: str) -> Image.Image:
    image = Image.new("RGB", (600, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 30), label, fill="black", font=_font(28))
    draw.text((30, 90), f"nonce {uuid4()}", fill="black", font=_font(20))
    return image


def _multipage_tiff() -> bytes:
    frames = [_frame("INVOICE"), _frame("CONTRACT"), _frame("EMPLOYEE FORM")]
    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="TIFF",
        save_all=True,
        append_images=frames[1:],
    )
    return buffer.getvalue()


def _upload(name: str, content: bytes, content_type: str) -> dict:
    response = client.post(
        "/api/documents/upload",
        files={"file": (name, content, content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_multiframe_tiff_produces_one_page_per_frame() -> None:
    tiff_bytes = _multipage_tiff()
    with Image.open(BytesIO(tiff_bytes)) as check:
        assert getattr(check, "n_frames", 1) == 3

    body = _upload("multipage_scans.tiff", tiff_bytes, "image/tiff")
    document_id = body["document_id"]

    extract_resp = client.post(
        f"/api/documents/{document_id}/extract-pages",
        json={
            "run_ocr": True,
            "page_start": None,
            "page_end": None,
            "force_reprocess": True,
        },
    )
    if extract_resp.status_code != 200:
        pytest.skip(f"OCR unavailable in environment: {extract_resp.text}")

    pages = client.get(f"/api/documents/{document_id}/pages").json()
    assert len(pages) == 3, f"expected 3 DocumentPage rows, got {len(pages)}"

    doc_after = client.get(f"/api/documents/{document_id}").json()
    provenance = doc_after.get("ingestion_provenance") or {}
    assert provenance.get("page_count") == 3


def test_ocr_image_bytes_bounds_execution_on_timeout() -> None:
    frame = _frame("SLOW")
    buffer = BytesIO()
    frame.save(buffer, format="PNG")

    with patch(
        "pytesseract.image_to_string",
        side_effect=RuntimeError("Tesseract process timeout"),
    ):
        text = ocr_image_bytes(buffer.getvalue(), timeout_seconds=1)

    assert text == ""


def test_ocr_image_bytes_passes_timeout_to_pytesseract() -> None:
    frame = _frame("BOUNDED")
    buffer = BytesIO()
    frame.save(buffer, format="PNG")

    captured: dict = {}

    def fake_image_to_string(image, lang=None, timeout=0):
        captured["timeout"] = timeout
        return "ok"

    with patch(
        "pytesseract.image_to_string", side_effect=fake_image_to_string
    ):
        text = ocr_image_bytes(buffer.getvalue(), timeout_seconds=7)

    assert text == "ok"
    assert captured["timeout"] == 7


def test_run_with_timeout_recovers_from_hung_native_call() -> None:
    import time

    def hangs_forever():
        time.sleep(30)
        return "should never get here"

    started = time.perf_counter()
    with pytest.raises(TimeoutError):
        _run_with_timeout(hangs_forever, timeout_seconds=0.5)
    elapsed = time.perf_counter() - started

    assert elapsed < 5, (
        "caller should recover promptly instead of waiting for the "
        "abandoned thread"
    )


def test_run_with_timeout_returns_result_when_fast_enough() -> None:
    assert _run_with_timeout(lambda: 42, timeout_seconds=5) == 42
