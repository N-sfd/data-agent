"""Step 2: normalized line/region model.

Confirmed root cause of Step 1's weak Contract Summary result: PyMuPDF's
"blocks" text mode merges several visually-separate SF33 item labels (and
separately, several item values) into one block whose bbox is the union of
all of them - "2. CONTRACT NUMBER" and "3. SOLICITATION NUMBER" can share
one block even though they sit in different columns. Classifying at block
granularity throws away the real per-line positions needed to pair a label
with its own value instead of a neighbor's.

This module adds a LINE-granularity view on top of the existing block
extraction - additive, not destructive (the original blocks/PageTextBlock
rows are untouched; nothing here requires a schema change). Three sources,
in preference order:

  1. `lines_from_fitz_page` - true per-line bboxes from PyMuPDF's "dict"
     text mode (confirmed: this alone resolves the SF33 pairing problem -
     "3. SOLICITATION NUMBER" and its value "47QRCA23R0001" land in
     matching x-columns at adjacent y-bands once real line bboxes are
     used, instead of being merged into one wide multi-label block).
  2. `lines_from_ocr_layout` - the OCR word/line layer already captured
     per page (`DocumentPage.ocr_layout_json`) for scanned pages; same
     shape, no new extraction needed.
  3. `lines_from_blocks_fallback` - when neither is available (e.g. only
     coarse PageTextBlock rows on hand, no OCR layout, no live fitz.Page),
     split each block's text on "\n" and interpolate a y-band per line
     across the block's own bbox height. Strictly worse than 1/2 - flags
     its own regions as lower-confidence via `source`.

`LogicalLine` intentionally satisfies `structure_classifier.BlockLike`
(text/x0/y0/x1/y1/block_type/extraction_method), so the Step 1 structure
classifier and candidate router work unchanged on lines instead of blocks -
no rewrite needed, just a finer-grained input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

LineSource = Literal["native_dict_span", "ocr_word_layer", "block_split_interpolated"]


@dataclass(frozen=True)
class LogicalLine:
    page_number: int
    parent_block_index: int
    line_index: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    extraction_method: str
    source: LineSource
    block_type: str = "text"
    confidence: float | None = None


def lines_from_fitz_page(
    *,
    page: Any,
    page_number: int,
    extraction_method: str = "native",
) -> list[LogicalLine]:
    """Real per-line bboxes from PyMuPDF's dict text mode. `page` is a
    fitz.Page - typed Any here to avoid a hard fitz import for callers that
    only use the other two line sources (e.g. pure OCR/fallback tests)."""

    lines: list[LogicalLine] = []
    text_dict = page.get_text("dict", sort=True)

    for block_index, block in enumerate(text_dict.get("blocks", [])):
        if block.get("type") != 0:  # 0 = text block, 1 = image block
            continue
        for line_index, line in enumerate(block.get("lines", [])):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            bbox = line.get("bbox")
            if not bbox:
                continue
            lines.append(
                LogicalLine(
                    page_number=page_number,
                    parent_block_index=block_index,
                    line_index=line_index,
                    text=text,
                    x0=float(bbox[0]),
                    y0=float(bbox[1]),
                    x1=float(bbox[2]),
                    y1=float(bbox[3]),
                    extraction_method=extraction_method,
                    source="native_dict_span",
                )
            )

    return lines


def lines_from_ocr_layout(
    *,
    ocr_layout_json: dict | None,
    page_number: int,
) -> list[LogicalLine]:
    """Real per-line bboxes for scanned pages, from the OCR word/line layer
    already captured at extraction time (app/services/ocr_word_layer.py) -
    no new OCR pass, just reading what was already produced."""

    if not ocr_layout_json:
        return []

    lines: list[LogicalLine] = []
    for line_index, line in enumerate(ocr_layout_json.get("lines", [])):
        text = str(line.get("text", "")).strip()
        if not text:
            continue
        lines.append(
            LogicalLine(
                page_number=page_number,
                parent_block_index=-1,  # OCR lines aren't grouped into our block model
                line_index=line_index,
                text=text,
                x0=float(line.get("x0", 0.0)),
                y0=float(line.get("y0", 0.0)),
                x1=float(line.get("x1", 0.0)),
                y1=float(line.get("y1", 0.0)),
                extraction_method="ocr",
                source="ocr_word_layer",
                confidence=line.get("conf"),
            )
        )
    return lines


def lines_from_blocks_fallback(
    *,
    blocks: list[Any],
    page_number: int,
) -> list[LogicalLine]:
    """Worst-case fallback when only coarse block data is available (no
    live fitz.Page, no OCR layout): split each block's text on newlines
    and interpolate a proportional y-band per line across the block's own
    bbox. x0/x1 are kept identical to the parent block (no real column
    information at this granularity) - callers should weight geometric
    matches from this source lower (`source == "block_split_interpolated"`)
    than the other two."""

    lines: list[LogicalLine] = []
    for block_index, block in enumerate(blocks):
        raw_lines = [line_text for line_text in block.text.split("\n") if line_text.strip()]
        if not raw_lines:
            continue

        block_height = block.y1 - block.y0
        line_height = block_height / len(raw_lines) if raw_lines else 0.0

        for line_index, line_text in enumerate(raw_lines):
            y0 = block.y0 + line_height * line_index
            y1 = y0 + line_height if line_height > 0 else block.y1
            lines.append(
                LogicalLine(
                    page_number=page_number,
                    parent_block_index=block_index,
                    line_index=line_index,
                    text=line_text.strip(),
                    x0=block.x0,
                    y0=y0,
                    x1=block.x1,
                    y1=y1,
                    extraction_method=getattr(block, "extraction_method", "native"),
                    source="block_split_interpolated",
                )
            )
    return lines


def best_available_lines(
    *,
    blocks: list[Any],
    page_number: int,
    fitz_page: Any | None = None,
    extraction_method: str = "native",
    ocr_layout_json: dict | None = None,
) -> list[LogicalLine]:
    """Picks the best line source available for this page, in preference
    order: live fitz.Page (native dict-mode) > captured OCR line layer >
    interpolated fallback from coarse blocks."""

    if fitz_page is not None:
        lines = lines_from_fitz_page(
            page=fitz_page, page_number=page_number, extraction_method=extraction_method
        )
        if lines:
            return lines

    if ocr_layout_json:
        lines = lines_from_ocr_layout(ocr_layout_json=ocr_layout_json, page_number=page_number)
        if lines:
            return lines

    return lines_from_blocks_fallback(blocks=blocks, page_number=page_number)
