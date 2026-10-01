"""Positioned text lines for every page of a contract, in PDF points, with
running page headers/footers ("N4019223D2803", "Page 12 of 33") removed so
they never leak into clause text or table rows."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.line_model import LogicalLine, best_available_lines
from app.services.v3_pipeline import _open_source_pdf
from app.source_structure.ocr_geometry import PageGeometry

_MARGIN_BAND = 75.0
_MIN_PAGES_FOR_RUNNING_LINES = 4
# Pages whose drawn form rules are collected (cover forms live up front).
RULED_PAGES = 5

# A horizontal rule is (x0, x1, y); a vertical rule is (y0, y1, x).
Rule = tuple[float, float, float]


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class PageLines:
    page_number: int
    width: float
    height: float
    lines: tuple[LogicalLine, ...]
    h_rules: tuple[Rule, ...] = ()
    v_rules: tuple[Rule, ...] = ()
    # Word boxes for column assignment (a PDF line can span a whole table
    # row). Native pages: PyMuPDF words; OCR pages: words split from lines.
    words: tuple[Word, ...] = ()


def words_from_lines(lines: list[LogicalLine]) -> list[Word]:
    """Approximate word boxes for OCR lines (proportional to characters)."""
    words: list[Word] = []
    for line in lines:
        width = max(line.x1 - line.x0, 1.0)
        per_char = width / max(len(line.text), 1)
        for match in re.finditer(r"\S+", line.text):
            words.append(
                Word(match.group(0), line.x0 + per_char * match.start(), line.y0,
                     line.x0 + per_char * match.end(), line.y1)
            )
    return words


def drawn_rules(fitz_page) -> tuple[list[Rule], list[Rule]]:
    """Horizontal and vertical form rules from a native PDF page's vector
    drawings (lines, hairline rectangles and box edges)."""
    horizontal: list[Rule] = []
    vertical: list[Rule] = []
    for drawing in fitz_page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l":
                a, b = item[1], item[2]
                if abs(a.y - b.y) < 1:
                    horizontal.append((min(a.x, b.x), max(a.x, b.x), (a.y + b.y) / 2))
                elif abs(a.x - b.x) < 1:
                    vertical.append((min(a.y, b.y), max(a.y, b.y), (a.x + b.x) / 2))
            elif item[0] == "re":
                r = item[1]
                if r.height < 2.5:
                    horizontal.append((r.x0, r.x1, (r.y0 + r.y1) / 2))
                elif r.width < 2.5:
                    vertical.append((r.y0, r.y1, (r.x0 + r.x1) / 2))
                else:
                    horizontal += [(r.x0, r.x1, r.y0), (r.x0, r.x1, r.y1)]
                    vertical += [(r.y0, r.y1, r.x0), (r.y0, r.y1, r.x1)]
    return horizontal, vertical


def compact(text: str) -> str:
    """Whitespace-free lowercase text: PDF text often splits words
    ("Off ers", "perf ormance")."""
    return re.sub(r"\s+", "", text).lower()


def _running_key(text: str) -> str:
    return re.sub(r"\d+", "#", compact(text))


def strip_running_lines(pages: list[PageLines]) -> list[PageLines]:
    """Drop lines that repeat (digits ignored) in the top or bottom margin
    of many pages — page headers, footers and page numbers."""
    if len(pages) < _MIN_PAGES_FOR_RUNNING_LINES:
        return pages

    def in_margin(page: PageLines, line: LogicalLine) -> bool:
        return line.y1 <= _MARGIN_BAND or line.y0 >= page.height - _MARGIN_BAND

    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({_running_key(line.text) for line in page.lines if in_margin(page, line)})
    threshold = max(3, int(len(pages) * 0.3))
    running = {key for key, count in counts.items() if count >= threshold and key}
    stripped: list[PageLines] = []
    for page in pages:
        dropped = [line for line in page.lines if in_margin(page, line) and _running_key(line.text) in running]
        kept = tuple(line for line in page.lines if line not in dropped)

        def covered(word: Word) -> bool:
            cx, cy = (word.x0 + word.x1) / 2, (word.y0 + word.y1) / 2
            return any(line.x0 - 1 <= cx <= line.x1 + 1 and line.y0 - 1 <= cy <= line.y1 + 1 for line in dropped)

        stripped.append(replace(page, lines=kept, words=tuple(word for word in page.words if not covered(word))))
    return stripped


def load_page_lines(
    database: Session,
    document: Document,
    *,
    max_page: int | None = None,
) -> list[PageLines]:
    """Native PDF text lines from the stored file; scanned pages fall back
    to the persisted OCR line layer converted out of OCR pixels."""
    if "pdf" not in (document.content_type or "").lower():
        return []
    query = select(DocumentPage).where(DocumentPage.document_id == document.id)
    if max_page is not None:
        query = query.where(DocumentPage.page_number <= max_page)
    pages = list(database.scalars(query.order_by(DocumentPage.page_number)))
    if not pages:
        return []

    geometry = PageGeometry(database, document.id)
    fitz_doc, _ = _open_source_pdf(document)
    result: list[PageLines] = []
    try:
        for page in pages:
            fitz_page = None
            width = float(page.page_width or 612.0)
            height = float(page.page_height or 792.0)
            if fitz_doc is not None and page.page_number <= fitz_doc.page_count:
                fitz_page = fitz_doc[page.page_number - 1]
                width, height = float(fitz_page.rect.width), float(fitz_page.rect.height)
            lines = best_available_lines(
                blocks=[],
                page_number=page.page_number,
                fitz_page=fitz_page,
                extraction_method=page.extraction_method or "native",
                ocr_layout_json=page.ocr_layout_json,
            )
            converted: list[LogicalLine] = []
            for line in lines:
                if line.source != "ocr_word_layer":
                    converted.append(line)
                    continue
                bbox = geometry.pdf_bbox(page.page_number, (line.x0, line.y0, line.x1, line.y1), "ocr_pixels")
                if bbox:
                    converted.append(replace(line, x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3]))
            converted.sort(key=lambda line: (round(line.y0, 1), line.x0))
            h_rules: list[Rule] = []
            v_rules: list[Rule] = []
            if fitz_page is not None and page.page_number <= RULED_PAGES:
                h_rules, v_rules = drawn_rules(fitz_page)
            native = converted and converted[0].source == "native_dict_span"
            words = (
                [Word(w[4], w[0], w[1], w[2], w[3]) for w in fitz_page.get_text("words")]
                if native and fitz_page is not None
                else words_from_lines(converted)
            )
            result.append(
                PageLines(page.page_number, width, height, tuple(converted), tuple(h_rules), tuple(v_rules), tuple(words))
            )
    finally:
        if fitz_doc is not None:
            fitz_doc.close()
    return result


def pdf_page_lines(fitz_doc) -> list[PageLines]:
    """PageLines for every page of an open native PDF, without the database
    (regression tests, tooling)."""
    from app.services.line_model import lines_from_fitz_page

    pages: list[PageLines] = []
    for index in range(fitz_doc.page_count):
        page = fitz_doc[index]
        lines = sorted(
            lines_from_fitz_page(page=page, page_number=index + 1), key=lambda line: (round(line.y0, 1), line.x0)
        )
        h_rules, v_rules = drawn_rules(page) if index + 1 <= RULED_PAGES else ([], [])
        words = [Word(w[4], w[0], w[1], w[2], w[3]) for w in page.get_text("words")]
        pages.append(
            PageLines(index + 1, page.rect.width, page.rect.height, tuple(lines), tuple(h_rules), tuple(v_rules), tuple(words))
        )
    return pages


_NEW_LINE_START = re.compile(r"^(\(?[a-z0-9]{1,4}\)|[-•*]|\(End of (clause|provision)\))", re.IGNORECASE)


def join_paragraphs(lines: list[LogicalLine]) -> str:
    """Source lines rejoined as the page reads: wrapped lines run on; a
    vertical gap starts a paragraph; list items, "(a)"/"(1)" sub-paragraphs
    and lines after a "HEADING:" start their own line."""
    text = ""
    previous: LogicalLine | None = None
    for line in lines:
        current = line.text.strip()
        if not current:
            continue
        if previous is None:
            text = current
        else:
            height = max(previous.y1 - previous.y0, 6.0)
            gap = line.y0 - previous.y1 if line.page_number == previous.page_number else 0.0
            if gap > 0.8 * height:
                text += "\n\n" + current
            elif _NEW_LINE_START.match(current) or previous.text.strip().endswith(":"):
                text += "\n" + current
            else:
                text += " " + current
        previous = line
    return text
