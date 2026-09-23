"""Step 1 structure detection: tags each extracted page block with what kind
of document structure it is, using only geometry + text signals already
produced by page extraction (no re-OCR, no re-render, no LLM call).

This exists to stop Table-of-Contents lines, section/subsection headings,
and page furniture (repeated footers/headers) from ever reaching field-value
candidate generation - confirmed via `docs/source-to-v3-mapping.md` as the
root cause of values like "NAICS -> Codes" and "B.8 -> 1 CONUS Standardized
Labor Categories" (both are literally fragments of Table-of-Contents lines).

Two passes:
  1. `build_document_context` - document-wide signals (which block texts
     repeat across many pages in a page margin -> footer/header template).
  2. `classify_page_regions` - per-page classification using the document
     context plus this page's own blocks/tables.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from app.schemas.candidate_classification import StructuralRegion, StructuralRegionType


class BlockLike(Protocol):
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_type: str
    extraction_method: str


_DIGIT_RE = re.compile(r"\d+")

# "B.8 LABOR CATEGORIES .......................................11" or
# "C.1.1 North American Industry Classification System....16" - a section
# identifier, a title, and a trailing page number, joined by either dot
# leaders or a wide whitespace gap.
_TOC_LINE_RE = re.compile(
    r"^(?P<num>(?:SECTION\s+[A-Z]\b|[A-Z]{1,2}(?:\.\d+){0,3}))"
    r"[\s.]{1,3}(?P<title>.{2,140}?)"
    r"(?:\.{2,}|\s{2,})\s*(?P<pagenum>\d{1,4})\s*$",
    re.IGNORECASE,
)

# A bare section-number prefix, used as a weaker secondary TOC signal on a
# page already flagged as TOC-dense (handles subsection fragments whose
# trailing page number didn't survive block splitting).
_SECTION_NUM_PREFIX_RE = re.compile(
    r"^(?:SECTION\s+[A-Z]\b|[A-Z]{1,2}(?:\.\d+){1,3})\b"
)

# A numbered heading: "B.8 LABOR CATEGORIES", "C.1 SCOPE", "SECTION C -
# DESCRIPTION/SPECIFICATIONS/STATEMENT OF WORK". Short, no TOC page-number
# tail, mostly capitalized.
_HEADING_RE = re.compile(
    r"^(?P<num>SECTION\s+[A-Z]\b|[A-Z]{1,2}(?:\.\d+){0,3})"
    r"\s*[-–—:]?\s*"
    r"(?P<title>[A-Z][A-Za-z0-9 &/,'()]{1,90})$"
)

# Clause-citation shape (FAR/DFARS/GSAR), used only to test how MUCH of a
# block the citation consumes - the actual clause scanning/matching lives in
# clause_citation_scanner.py. Kept in sync with that module's patterns.
_CLAUSE_NUMBER_RE = re.compile(r"\b(?:52|252|552)\.\d{3}-\d+\b")

# Numbered SF-33-style form item label: "2. CONTRACT NUMBER", "3. SOLICITATION
# NUMBER", "7. ISSUED BY".
_FORM_LABEL_RE = re.compile(
    r"^\d{1,2}[A-Za-z]?\.\s+[A-Z][A-Z0-9 /()\-.,]{1,70}$"
)

_STOPWORDS = frozenset(
    "the a an of to in on for and or but is are was were be been being "
    "this that these those shall will would should may might must not "
    "whether if as by with from at it its their his her our your".split()
)

_TOC_DENSITY_THRESHOLD = 3


@dataclass(frozen=True)
class DocumentContext:
    """Cross-page signals computed once per document."""

    footer_header_templates: frozenset[str] = field(default_factory=frozenset)
    toc_pages: frozenset[int] = field(default_factory=frozenset)


def _normalize_for_repetition(text: str) -> str:
    return _DIGIT_RE.sub("#", text.strip().lower())


def build_document_context(
    *,
    pages: list[tuple[int, list[BlockLike], float]],
) -> DocumentContext:
    """pages: list of (page_number, blocks, page_height)."""

    if not pages:
        return DocumentContext()

    margin_texts: Counter[str] = Counter()
    margin_pages: dict[str, set[int]] = {}

    for page_number, blocks, page_height in pages:
        if page_height <= 0:
            continue
        top_band = page_height * 0.10
        bottom_band = page_height * 0.90
        for block in blocks:
            in_margin = block.y0 <= top_band or block.y1 >= bottom_band
            if not in_margin:
                continue
            text = block.text.strip()
            if not text or len(text) > 160:
                continue
            key = _normalize_for_repetition(text)
            margin_texts[key] += 1
            margin_pages.setdefault(key, set()).add(page_number)

    total_pages = len(pages)
    min_repeats = max(3, int(total_pages * 0.25))
    templates = frozenset(
        key
        for key, pages_seen in margin_pages.items()
        if len(pages_seen) >= min_repeats
    )

    toc_pages: set[int] = set()
    for page_number, blocks, _height in pages:
        toc_line_hits = sum(1 for b in blocks if _TOC_LINE_RE.match(b.text.strip()))
        has_toc_banner = any(
            "table of contents" in b.text.strip().lower() for b in blocks
        )
        if toc_line_hits >= _TOC_DENSITY_THRESHOLD or (
            has_toc_banner and toc_line_hits >= 1
        ):
            toc_pages.add(page_number)

    return DocumentContext(
        footer_header_templates=templates,
        toc_pages=toc_pages,
    )


def _match_table_cell_text(
    text: str,
    tables: list[dict],
) -> tuple[bool, bool]:
    """Returns (matches_header, matches_row) for a normalized block text
    against any detected table on this page."""

    normalized = _normalize_for_repetition(text)
    if not normalized:
        return False, False

    for table in tables or []:
        headers = [str(h) for h in (table.get("headers") or [])]
        header_concat = _normalize_for_repetition(" ".join(headers))
        if header_concat and (
            normalized == header_concat or normalized in header_concat
        ):
            return True, False

        for row in table.get("rows") or []:
            if isinstance(row, dict):
                values = [str(v) for v in row.values() if v is not None]
            elif isinstance(row, (list, tuple)):
                values = [str(v) for v in row if v is not None]
            else:
                continue
            row_concat = _normalize_for_repetition(" ".join(values))
            if row_concat and (
                normalized == row_concat or normalized in row_concat
            ):
                return False, True

    return False, False


def _has_degenerate_geometry(blocks: list[BlockLike]) -> bool:
    coords = {(b.x0, b.y0, b.x1, b.y1) for b in blocks}
    return len(coords) <= 1


def _looks_like_prose(text: str) -> bool:
    words = text.split()
    if len(words) < 6:
        return False
    stopword_hits = sum(1 for w in words if w.lower().strip(",.;:") in _STOPWORDS)
    return stopword_hits >= 2 or text.rstrip().endswith((".", ";"))


def classify_page_regions(
    *,
    page_number: int,
    blocks: list[BlockLike],
    tables: list[dict] | None,
    page_height: float,
    doc_context: DocumentContext | None = None,
) -> list[StructuralRegion]:
    context = doc_context or DocumentContext()
    tables = tables or []
    page_is_toc_dense = page_number in context.toc_pages
    degenerate_geometry = _has_degenerate_geometry(blocks) if blocks else True

    regions: list[StructuralRegion] = []

    for index, block in enumerate(blocks):
        text = block.text.strip()
        if not text:
            continue
        bbox = (block.x0, block.y0, block.x1, block.y1)
        extraction_method = getattr(block, "extraction_method", "native")

        region_type: StructuralRegionType
        confidence: float
        reasons: list[str] = []

        normalized_key = _normalize_for_repetition(text)
        is_margin = page_height > 0 and (
            block.y0 <= page_height * 0.10 or block.y1 >= page_height * 0.90
        )

        if is_margin and normalized_key in context.footer_header_templates:
            region_type = "FOOTER_HEADER"
            confidence = 0.9
            reasons = ["repeated_across_pages_margin_band"]

        elif _TOC_LINE_RE.match(text):
            region_type = "TOC_ENTRY"
            confidence = 0.95
            reasons = ["toc_line_shape_number_title_pagenum"]

        elif page_is_toc_dense and _SECTION_NUM_PREFIX_RE.match(text):
            region_type = "TOC_ENTRY"
            confidence = 0.7
            reasons = ["toc_context_page_density", "section_number_prefix"]

        elif (header_hit := _match_table_cell_text(text, tables))[0]:
            region_type = "TABLE_HEADER"
            confidence = 0.9
            reasons = ["matches_detected_table_header"]

        elif header_hit[1]:
            region_type = "TABLE_ROW"
            confidence = 0.9
            reasons = ["matches_detected_table_row"]

        elif _HEADING_RE.match(text) and len(text.split()) <= 14:
            match = _HEADING_RE.match(text)
            num = match.group("num") if match else ""
            dot_count = num.count(".")
            if dot_count == 0:
                region_type = "SECTION_HEADING"
            else:
                region_type = "SUBSECTION_HEADING"
            confidence = 0.85
            reasons = ["numbered_heading_shape"]

        elif _CLAUSE_NUMBER_RE.search(text) and len(text.split()) <= 15:
            match = _CLAUSE_NUMBER_RE.search(text)
            starts_near_beginning = bool(match) and match.start() <= 5
            region_type = "CLAUSE_LISTING"
            confidence = 0.9 if starts_near_beginning else 0.65
            reasons = ["clause_number_dominant_short_block"]

        elif _FORM_LABEL_RE.match(text):
            region_type = "FORM_FIELD_LABEL"
            confidence = 0.8
            reasons = ["numbered_form_item_label_shape"]

        elif len(text.split()) <= 8 and not _looks_like_prose(text):
            # Short, non-prose fragment: candidate form-field VALUE if it
            # sits near a label (checked by the router, not here - this
            # module only tags shape, not pairing).
            region_type = "FORM_FIELD_VALUE"
            confidence = 0.55 if not degenerate_geometry else 0.4
            reasons = ["short_non_prose_fragment"]
            if degenerate_geometry:
                reasons.append("degenerate_geometry_fallback")

        elif _looks_like_prose(text) or len(text.split()) > 8:
            region_type = "NARRATIVE"
            confidence = 0.75
            reasons = ["prose_shape_or_long_block"]

        else:
            region_type = "OTHER"
            confidence = 0.3
            reasons = ["unclassified_fragment"]

        regions.append(
            StructuralRegion(
                page_number=page_number,
                block_index=index,
                region_type=region_type,
                text=text,
                bbox=bbox,
                confidence=confidence,
                reason_codes=reasons,
                extraction_method=extraction_method,
            )
        )

    return regions
