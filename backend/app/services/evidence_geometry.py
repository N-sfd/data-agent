"""Candidate bounding boxes persisted as source evidence, with their
coordinate space.

Native-text line geometry (PyMuPDF) is in PDF points — the renderer's
space. OCR line geometry is in the OCR raster's pixels; it is stored as-is
and tagged "ocr_pixels" so readers can map it to PDF points with
app/source_structure/ocr_geometry.py rather than discarding it.
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


def evidence_bbox(candidate: _HasGeometry) -> dict:
    """{"bbox": [...], "bbox_space": "pdf_points" | "ocr_pixels"} for
    evidence_json, or {"bbox": None}."""

    if not candidate.bbox:
        return {"bbox": None}
    return {
        "bbox": [float(value) for value in candidate.bbox],
        "bbox_space": "ocr_pixels" if candidate.extraction_method == "ocr" else "pdf_points",
    }
