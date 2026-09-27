"""OCR pixel geometry → PDF points (the page renderer's space).

The OCR word layer (app/services/ocr_word_layer.py) reads a page raster
rendered at `dpi` and optionally deskewed by a small rotation about the
image centre (image_preprocess: `rotate(angle, expand=False)`, recorded as
a "deskew_+1.2" tag). So one pixel box maps back to the page by:

    1. undoing the deskew rotation about the image centre
    2. scaling by 72 / dpi

New layouts record their `coordinate_space`; for layouts captured before
that, the DPI is re-derived with the same formula the extractor used.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.source_structure.models import BBox

# Mirrors page_text_extractor: layout DPI = min(bounded OCR DPI, 220), where
# the bound keeps the raster's long side under MAX_OCR_RASTER_DIMENSION_PX.
_LAYOUT_DPI_CAP = 220
_DESKEW_TAG = re.compile(r"^deskew_([+-]?\d+(?:\.\d+)?)$")


@dataclass(frozen=True)
class OcrCoordinateSpace:
    dpi: float
    image_width: float
    image_height: float
    deskew_degrees: float = 0.0

    def to_pdf_points(self, bbox: tuple[float, float, float, float]) -> BBox:
        x0, y0, x1, y1 = bbox
        cx, cy = self.image_width / 2.0, self.image_height / 2.0
        if self.deskew_degrees:
            # PIL rotates counter-clockwise by +angle (y axis down), so the
            # original position is the rotated one turned back by -angle.
            theta = math.radians(self.deskew_degrees)
            cos_t, sin_t = math.cos(theta), math.sin(theta)
            points = []
            for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                dx, dy = px - cx, py - cy
                points.append((cx + dx * cos_t - dy * sin_t, cy + dx * sin_t + dy * cos_t))
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        scale = 72.0 / self.dpi
        return (x0 * scale, y0 * scale, x1 * scale, y1 * scale)


def _deskew_from_tags(tags) -> float:
    for tag in tags or []:
        match = _DESKEW_TAG.match(str(tag))
        if match:
            return float(match.group(1))
    return 0.0


def inferred_layout_dpi(page_width_pt: float, page_height_pt: float, ocr_dpi: int) -> float:
    from app.services.page_text_extractor import MAX_OCR_RASTER_DIMENSION_PX

    long_side = max(page_width_pt or 0.0, page_height_pt or 0.0)
    bounded = ocr_dpi
    if long_side > 0:
        bounded = max(1, min(ocr_dpi, int(MAX_OCR_RASTER_DIMENSION_PX * 72.0 / long_side)))
    return float(min(bounded, _LAYOUT_DPI_CAP))


def coordinate_space_for(
    ocr_layout_json: dict | None,
    *,
    page_width_pt: float,
    page_height_pt: float,
    ocr_dpi: int,
) -> OcrCoordinateSpace | None:
    if not ocr_layout_json:
        return None
    recorded = ocr_layout_json.get("coordinate_space") or {}
    deskew = recorded.get("deskew_degrees")
    if deskew is None:
        deskew = _deskew_from_tags(ocr_layout_json.get("preprocess"))
    dpi = recorded.get("dpi") or inferred_layout_dpi(page_width_pt, page_height_pt, ocr_dpi)
    width = recorded.get("image_width") or round(page_width_pt * dpi / 72.0)
    height = recorded.get("image_height") or round(page_height_pt * dpi / 72.0)
    return OcrCoordinateSpace(
        dpi=float(dpi),
        image_width=float(width),
        image_height=float(height),
        deskew_degrees=float(deskew),
    )


class PageGeometry:
    """Maps persisted evidence boxes to PDF points for one document,
    loading a page's OCR coordinate space only when an OCR box needs it."""

    def __init__(self, database, document_id: str):
        self.database = database
        self.document_id = document_id
        self._spaces: dict[int, OcrCoordinateSpace | None] = {}

    def _space(self, page_number: int) -> OcrCoordinateSpace | None:
        if page_number not in self._spaces:
            from sqlalchemy import select

            from app.core.config import get_settings
            from app.models.document_page import DocumentPage

            page = self.database.scalars(
                select(DocumentPage).where(
                    DocumentPage.document_id == self.document_id,
                    DocumentPage.page_number == page_number,
                )
            ).first()
            self._spaces[page_number] = (
                coordinate_space_for(
                    page.ocr_layout_json,
                    page_width_pt=page.page_width or 612.0,
                    page_height_pt=page.page_height or 792.0,
                    ocr_dpi=get_settings().ocr_dpi,
                )
                if page is not None
                else None
            )
        return self._spaces[page_number]

    def pdf_bbox(self, page_number: int | None, bbox, space: str | None):
        if not bbox or len(bbox) != 4:
            return None
        if space != "ocr_pixels":
            return tuple(float(v) for v in bbox)
        if page_number is None:
            return None
        coordinate_space = self._space(page_number)
        if coordinate_space is None:
            return None
        return coordinate_space.to_pdf_points(tuple(float(v) for v in bbox))
