"""Targeted second-pass OCR on a cropped field/table region.

Avoids re-running high-resolution OCR across an entire multi-page scan.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from app.core.observability import log_event
from app.services.embedded_image_ocr import ocr_image_bytes
from app.services.image_preprocess import preprocess_scan_image


@dataclass(frozen=True)
class TargetedOcrResult:
    text: str
    raw_ocr: str
    bbox: tuple[float, float, float, float]
    scale: float
    method: str = "targeted_crop_ocr"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def crop_and_ocr(
    page_image_bytes: bytes,
    *,
    bbox: tuple[float, float, float, float],
    page_width: float,
    page_height: float,
    language: str = "eng",
    pad_ratio: float = 0.08,
    target_min_edge_px: int = 900,
    timeout_seconds: int = 30,
) -> TargetedOcrResult:
    """Crop ``bbox`` (page coordinates) from a rendered page and OCR it."""

    from PIL import Image

    image = Image.open(BytesIO(page_image_bytes)).convert("RGB")
    img_w, img_h = image.size
    scale_x = img_w / max(page_width, 1.0)
    scale_y = img_h / max(page_height, 1.0)

    x0, y0, x1, y1 = bbox
    pad_x = (x1 - x0) * pad_ratio
    pad_y = (y1 - y0) * pad_ratio
    left = int(_clamp((x0 - pad_x) * scale_x, 0, img_w - 1))
    top = int(_clamp((y0 - pad_y) * scale_y, 0, img_h - 1))
    right = int(_clamp((x1 + pad_x) * scale_x, left + 1, img_w))
    bottom = int(_clamp((y1 + pad_y) * scale_y, top + 1, img_h))

    crop = image.crop((left, top, right, bottom))
    # Upscale small crops so Tesseract has enough pixels — without
    # exceeding a modest bound (fits the raster protection posture).
    cw, ch = crop.size
    scale = 1.0
    edge = max(cw, ch)
    if edge < target_min_edge_px and edge > 0:
        scale = min(3.0, target_min_edge_px / edge)
        crop = crop.resize(
            (max(1, int(cw * scale)), max(1, int(ch * scale))),
            Image.Resampling.LANCZOS,
        )

    buffer = BytesIO()
    crop.save(buffer, format="PNG")
    prepared = preprocess_scan_image(buffer.getvalue(), force=True)
    text = ocr_image_bytes(
        prepared.image_bytes,
        language=language,
        timeout_seconds=timeout_seconds,
    )
    log_event(
        "targeted_ocr",
        stage="rendering_ocr",
        status="ok" if text else "empty",
        text_chars=len(text),
        scale=round(scale, 2),
        preprocess=prepared.applied[:6],
    )
    return TargetedOcrResult(
        text=text,
        raw_ocr=text,
        bbox=bbox,
        scale=scale,
    )
