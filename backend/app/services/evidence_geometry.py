"""Which candidate bounding boxes are safe to persist as source evidence.

Native-text line geometry (PyMuPDF) is in PDF points — the same space the
page renderer highlights in. OCR line geometry is in the rendered image's
pixel space, so persisting it as a PDF-point bbox would highlight the wrong
region; those candidates keep page + evidence text only.
"""

from __future__ import annotations

from typing import Protocol


class _HasGeometry(Protocol):
    bbox: tuple[float, float, float, float] | None
    extraction_method: str


def pdf_point_bbox(candidate: _HasGeometry) -> list[float] | None:
    if not candidate.bbox or candidate.extraction_method == "ocr":
        return None
    return [float(value) for value in candidate.bbox]
