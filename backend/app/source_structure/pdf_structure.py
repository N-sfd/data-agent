"""PDF (native text or OCR words) → structural regions and candidates.

    words (PDF points, font size, bold)          native: PyMuPDF words+spans
        → visual lines (vertical overlap)         OCR:    word layer, mapped
        → segments (whitespace gaps)                      to PDF points
        → tables       ruling lines (find_tables) / column alignment
        → label/value  separator, left/right, label-above, typography,
                       AcroForm widgets
        → headings, paragraphs/narrative, contact blocks, key/value groups

Nothing here reads page text as one flat string before deciding structure:
every decision is made on positioned segments, and every region keeps its
bbox.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from app.services.table_quality import assess_table_candidate
from app.source_structure.models import (
    BBox,
    FieldCandidate,
    StructuredRegion,
    TableCandidate,
    TableCell,
)
from app.source_structure.ocr_geometry import OcrCoordinateSpace
from app.source_structure.table_hints import annotate_table
from app.source_structure.text_shapes import (
    candidate_quality,
    infer_value_type,
    is_numeric_value,
    label_rejection,
    normalize_space,
    strip_label_separator,
    value_rejection,
)


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool = False
    # Vertical offset of this word's row caused by page skew (a scanned
    # page tilted and not deskewed). Lines are grouped on y - row_offset;
    # the reported geometry stays in page space.
    row_offset: float = 0.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def row_y0(self) -> float:
        return self.y0 - self.row_offset

    @property
    def row_y1(self) -> float:
        return self.y1 - self.row_offset


@dataclass
class Segment:
    words: list[Word]
    line_index: int
    index: int = 0
    used: bool = False

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def bbox(self) -> BBox:
        return (
            min(w.x0 for w in self.words),
            min(w.y0 for w in self.words),
            max(w.x1 for w in self.words),
            max(w.y1 for w in self.words),
        )

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def size(self) -> float:
        return statistics.median(w.size for w in self.words)

    @property
    def bold(self) -> bool:
        return all(w.bold for w in self.words)


@dataclass
class Line:
    index: int
    words: list[Word] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)

    @property
    def y0(self) -> float:
        return min(w.y0 for w in self.words)

    @property
    def y1(self) -> float:
        return max(w.y1 for w in self.words)

    @property
    def height(self) -> float:
        return max(1.0, self.y1 - self.y0)

    @property
    def row_y0(self) -> float:
        return min(w.row_y0 for w in self.words)

    @property
    def row_y1(self) -> float:
        return max(w.row_y1 for w in self.words)

    @property
    def row_height(self) -> float:
        return max(1.0, self.row_y1 - self.row_y0)

    @property
    def free_segments(self) -> list[Segment]:
        return [s for s in self.segments if not s.used]


def _union(boxes: list[BBox]) -> BBox | None:
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


# --- word acquisition ----------------------------------------------------


def native_words(page) -> list[Word]:
    spans = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                font = str(span.get("font", ""))
                bold = bool(span.get("flags", 0) & 16) or "bold" in font.lower() or font.lower().endswith(("-bd", "bo"))
                spans.append((span["bbox"], float(span.get("size", 10.0)), bold))

    words: list[Word] = []
    for x0, y0, x1, y1, text, *_ in page.get_text("words"):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        size, bold = y1 - y0, False
        for (sx0, sy0, sx1, sy1), span_size, span_bold in spans:
            if sx0 - 0.5 <= cx <= sx1 + 0.5 and sy0 - 0.5 <= cy <= sy1 + 0.5:
                size, bold = span_size, span_bold
                break
        # Fonts that encode the printed hyphen as U+00AD (soft hyphen) would
        # otherwise yield values browsers render without the hyphen.
        words.append(Word(text.replace("\u00ad", "-"), x0, y0, x1, y1, size, bold))
    return words


def ocr_words(ocr_layout_json: dict, space: OcrCoordinateSpace) -> list[Word]:
    words: list[Word] = []
    for item in ocr_layout_json.get("words") or []:
        text = str(item.get("text") or "").strip()
        # Lone punctuation specks are a common OCR artifact ("Bill . To:").
        if not text or re.fullmatch(r"[.,'`|_~‘’]", text):
            continue
        x0, y0, x1, y1 = space.to_pdf_points(
            (float(item["x0"]), float(item["y0"]), float(item["x1"]), float(item["y1"]))
        )
        words.append(Word(text, x0, y0, x1, y1, size=max(1.0, (y1 - y0) * 0.85)))
    slope = ocr_skew_slope(ocr_layout_json)
    if slope and words:
        centre = (min(w.x0 for w in words) + max(w.x1 for w in words)) / 2
        for word in words:
            word.row_offset = slope * ((word.x0 + word.x1) / 2 - centre)
    return words


def ocr_skew_slope(ocr_layout_json: dict) -> float:
    """dy/dx of text rows on a page that was OCR'd still tilted (deskew
    skipped or not recorded): the median slope of word centres along the
    engine's own wide text lines. 0.0 when level or not measurable."""

    slopes: list[float] = []
    for line in ocr_layout_json.get("lines") or []:
        words = [w for w in line.get("words") or [] if str(w.get("text") or "").strip()]
        if len(words) < 3:
            continue
        xs = [(float(w["x0"]) + float(w["x1"])) / 2 for w in words]
        ys = [(float(w["y0"]) + float(w["y1"])) / 2 for w in words]
        span = max(xs) - min(xs)
        heights = [float(w["y1"]) - float(w["y0"]) for w in words]
        if span < 10 * statistics.median(heights):
            continue
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        denominator = sum((x - mx) ** 2 for x in xs)
        if denominator:
            slopes.append(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator)
    if len(slopes) < 3:
        return 0.0
    slope = statistics.median(slopes)
    # Ignore sub-0.1° noise and anything too steep to be a mild scan tilt.
    return slope if 0.0017 <= abs(slope) <= 0.09 else 0.0


# --- lines and segments ----------------------------------------------------


def build_lines(words: list[Word]) -> list[Line]:
    lines: list[Line] = []
    for word in sorted(words, key=lambda w: ((w.row_y0 + w.row_y1) / 2, w.x0)):
        height = max(1.0, word.y1 - word.y0)
        target = None
        for line in reversed(lines[-6:]):
            overlap = min(line.row_y1, word.row_y1) - max(line.row_y0, word.row_y0)
            if overlap >= 0.5 * min(line.row_height, height):
                target = line
                break
        if target is None:
            target = Line(index=len(lines))
            lines.append(target)
        target.words.append(word)

    lines.sort(key=lambda l: (l.row_y0, min(w.x0 for w in l.words)))
    for index, line in enumerate(lines):
        line.index = index
        ordered = sorted(line.words, key=lambda w: w.x0)
        current = [ordered[0]]
        segments = []
        # The line's typical glyph size, so one tiny token (an OCR speck, a
        # superscript) doesn't shrink the word-gap threshold.
        line_size = statistics.median(w.size for w in ordered)
        for prev, word in zip(ordered, ordered[1:]):
            gap = word.x0 - prev.x1
            size = max(prev.size, word.size, line_size, 1.0)
            if gap > 0.9 * size or (prev.bold != word.bold and gap > 0.2 * size and prev.text.endswith(":")):
                segments.append(Segment(current, index))
                current = [word]
            else:
                current.append(word)
        segments.append(Segment(current, index))
        for seg_index, seg in enumerate(segments):
            seg.index = seg_index
        line.segments = segments
    return lines


# --- tables: column alignment ----------------------------------------------


@dataclass
class _Band:
    x0: float
    x1: float

    def overlaps(self, seg: Segment, tolerance: float = 3.0) -> bool:
        return seg.x0 <= self.x1 + tolerance and seg.x1 >= self.x0 - tolerance


def _map_to_bands(line: Line, bands: list[_Band]) -> dict[int, list[Segment]] | None:
    mapping: dict[int, list[Segment]] = {}
    for seg in line.free_segments:
        hits = [i for i, band in enumerate(bands) if band.overlaps(seg)]
        if len(hits) != 1:
            return None
        mapping.setdefault(hits[0], []).append(seg)
    return mapping


_ROW_NUMBER = re.compile(r"^\(?\d{1,3}[.)]?$")


def _alignment_tables(lines: list[Line]) -> list[tuple[list[_Band], list[list[list[Segment]]], list[Line]]]:
    """Groups of consecutive lines whose segments line up in ≥3 columns.
    Returns (bands, rows[row][col] -> segments, lines) per table."""

    tables = []
    i = 0
    while i < len(lines):
        start = lines[i]
        if len(start.free_segments) < 3:
            i += 1
            continue
        bands = [_Band(s.x0, s.x1) for s in start.free_segments]
        rows: list[dict[int, list[Segment]]] = [
            {k: [s] for k, s in enumerate(start.free_segments)}
        ]
        members = [start]
        j = i + 1
        line_height = start.height
        while j < len(lines):
            line = lines[j]
            gap = line.y0 - members[-1].y1
            if gap > 2.5 * line_height or not line.free_segments:
                break
            mapping = _map_to_bands(line, bands)
            if mapping is None:
                break
            # A lone row number in the first column ("8." whose other cells
            # OCR lost) starts its own row; it is never wrapped cell text.
            lone_row_number = (
                len(line.free_segments) == 1
                and set(mapping) == {0}
                and bool(_ROW_NUMBER.match(line.free_segments[0].text.strip()))
            )
            if len(line.free_segments) >= 2 or lone_row_number:
                for band_index, segs in mapping.items():
                    bands[band_index].x0 = min(bands[band_index].x0, *(s.x0 for s in segs))
                    bands[band_index].x1 = max(bands[band_index].x1, *(s.x1 for s in segs))
                rows.append(mapping)
            elif gap <= 1.2 * line_height and len(rows) > 1:
                # Wrapped cell text (e.g. a long description) continues the
                # previous row rather than starting a new one.
                for band_index, segs in mapping.items():
                    rows[-1].setdefault(band_index, []).extend(segs)
            else:
                break
            members.append(line)
            j += 1

        full_rows = [r for r in rows if len(r) >= max(2, len(bands) // 2)]
        if len(bands) >= 3 and len(full_rows) >= 3:
            grid = [[row.get(b, []) for b in range(len(bands))] for row in rows]
            header = _header_above(lines, i, bands, line_height)
            if header is not None:
                grid.insert(0, header[1])
                members.insert(0, header[0])
            bands, grid = _split_fused_bands(bands, grid)
            tables.append((bands, grid, members))
            i = j
        else:
            i += 1
    return tables


def _header_above(
    lines: list[Line], start: int, bands: list[_Band], line_height: float
) -> tuple[Line, list[list[Segment]]] | None:
    """The line directly above a column-aligned table whose labels didn't
    band-align with the data (left-aligned headers over right-aligned
    numbers): same column count, label-shaped, and each label sits in its
    own column's slot — between the neighbouring columns — in order."""

    if start == 0:
        return None
    line = lines[start - 1]
    segs = sorted(line.free_segments, key=lambda s: s.x0)
    if len(segs) != len(bands) or lines[start].y0 - line.y1 > 1.5 * line_height:
        return None
    if any(is_numeric_value(s.text) or len(s.words) > 4 for s in segs):
        return None
    for k, seg in enumerate(segs):
        low = bands[k - 1].x1 if k else float("-inf")
        high = bands[k + 1].x0 if k + 1 < len(bands) else float("inf")
        if not (seg.x0 >= low - 2 and seg.x1 <= high + 2):
            return None
    return line, [[seg] for seg in segs]


def _split_fused_bands(
    bands: list[_Band], grid: list[list[list[Segment]]]
) -> tuple[list[_Band], list[list[list[Segment]]]]:
    """Two columns whose HEADERS nearly touch ("UOM" + right-aligned "Unit
    Price") fuse into one band, yet every data row shows two runs with a
    clear vertical gutter between them. Split such a band at that gutter;
    a header run that straddles it is divided word by word."""

    b = 0
    while b < len(bands):
        cells = [row[b] for row in grid]
        filled = [c for c in cells if c]
        pairs = [sorted(c, key=lambda s: s.x0) for c in filled if len(c) == 2]
        if len(pairs) < 3 or len(pairs) < 0.6 * len(filled) or any(len(c) > 2 for c in filled):
            b += 1
            continue
        g0 = max(p[0].x1 for p in pairs)
        g1 = min(p[1].x0 for p in pairs)
        singles = [c[0] for c in filled if len(c) == 1]
        straddling = [s for s in singles if s.x0 < g0 - 1 and s.x1 > g1 + 1]
        if g1 - g0 < 4 or len(straddling) > 1:
            b += 1
            continue
        middle = (g0 + g1) / 2
        new_grid = []
        for row in grid:
            left: list[Segment] = []
            right: list[Segment] = []
            for seg in row[b]:
                if seg.x1 <= middle:
                    left.append(seg)
                elif seg.x0 >= middle:
                    right.append(seg)
                else:
                    # A header run spanning the gutter: assign each word to
                    # the side whose data it sits nearer to.
                    lw = [w for w in seg.words if (w.x0 + w.x1) / 2 < middle]
                    rw = [w for w in seg.words if (w.x0 + w.x1) / 2 >= middle]
                    if lw:
                        left.append(Segment(lw, seg.line_index, seg.index, seg.used))
                    if rw:
                        right.append(Segment(rw, seg.line_index, seg.index, seg.used))
            new_grid.append(row[:b] + [left, right] + row[b + 1:])
        grid = new_grid
        band = bands[b]
        bands = bands[:b] + [_Band(band.x0, g0), _Band(g1, band.x1)] + bands[b + 1:]
        b += 2
    return bands, grid


def _is_header_row(cells: list[list[Segment]], data_rows: list[list[list[Segment]]]) -> bool:
    texts = [" ".join(s.text for s in cell) for cell in cells]
    filled = [t for t in texts if t]
    if len(filled) < 2 or any(is_numeric_value(t) for t in filled):
        return False
    if any(len(t.split()) > 4 for t in filled):
        return False
    data_numeric = any(
        is_numeric_value(" ".join(s.text for s in row[c]))
        for row in data_rows
        for c in range(len(row))
    )
    bold = all(seg.bold for cell in cells for seg in cell)
    return bold or data_numeric


# --- tables: ruling lines (native PDF tables) --------------------------------


def _ruled_tables(page, page_number: int):
    try:
        # lines_strict: only real vector rules form cell borders — text
        # background rectangles don't invent columns.
        found = page.find_tables(strategy="lines_strict")
    except Exception:  # noqa: BLE001 - table finder is best-effort
        return []
    results = []
    for tab in found.tables:
        try:
            data = tab.extract()
        except Exception:  # noqa: BLE001
            continue
        if not data or len(data) < 2 or tab.col_count < 2:
            continue
        cell_boxes = [list(row.cells) for row in tab.rows]
        results.append((tab.bbox, data, cell_boxes, list(tab.header.names or [])))
    return results


# --- the extractor --------------------------------------------------------------


@dataclass
class PageStructure:
    regions: list[StructuredRegion] = field(default_factory=list)
    fields: list[FieldCandidate] = field(default_factory=list)
    tables: list[TableCandidate] = field(default_factory=list)


class _Ids:
    def __init__(self, page: int):
        self.page = page
        self.counts: dict[str, int] = {}

    def next(self, kind: str) -> str:
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return f"p{self.page}:{kind}:{self.counts[kind]}"


def _cell_text(segs: list[Segment]) -> str:
    return normalize_space(" ".join(s.text for s in segs))


def _table_from_grid(
    ids: _Ids,
    page_number: int,
    method: str,
    extraction_method: str,
    header_texts: list[str] | None,
    header_boxes: list[BBox | None],
    body_texts: list[list[str]],
    body_boxes: list[list[BBox | None]],
    page_text: str,
    bbox: BBox | None,
) -> tuple[TableCandidate, list[StructuredRegion]]:
    region_id = ids.next("table")
    columns = max(len(r) for r in body_texts) if body_texts else len(header_texts or [])
    headers = header_texts or [f"Column {i + 1}" for i in range(columns)]
    regions: list[StructuredRegion] = []
    header_cells = [
        TableCell(row_index=-1, column_index=c, text=headers[c], bbox=header_boxes[c] if c < len(header_boxes) else None)
        for c in range(len(headers))
    ] if header_texts else []
    rows: list[list[TableCell]] = []
    for r, (texts, boxes) in enumerate(zip(body_texts, body_boxes)):
        row_id = f"{region_id}:r{r}"
        cells = []
        for c, text in enumerate(texts):
            cell_id = f"{row_id}:c{c}"
            cells.append(
                TableCell(row_index=r, column_index=c, text=text, bbox=boxes[c] if c < len(boxes) else None, region_id=cell_id)
            )
            if text:
                regions.append(
                    StructuredRegion(
                        region_id=cell_id,
                        region_type="TABLE_CELL",
                        text=text,
                        normalized_text=text.lower(),
                        page=page_number,
                        bbox=boxes[c] if c < len(boxes) else None,
                        parent_region_id=row_id,
                        extraction_method=extraction_method,
                        structural_metadata={"row_index": r, "column_index": c},
                    )
                )
        rows.append(cells)
        regions.append(
            StructuredRegion(
                region_id=row_id,
                region_type="TABLE_ROW",
                text=" | ".join(texts),
                normalized_text=" | ".join(texts).lower(),
                page=page_number,
                bbox=_union([b for b in boxes if b]),
                parent_region_id=region_id,
                children=[f"{row_id}:c{c}" for c, t in enumerate(texts) if t],
                extraction_method=extraction_method,
                structural_metadata={"row_index": r},
            )
        )

    assessment = assess_table_candidate(
        headers=headers, rows=[[c.text for c in row] for row in rows], page_text=page_text
    )
    table = TableCandidate(
        candidate_id=region_id,
        region_id=region_id,
        page=page_number,
        bbox=bbox,
        detection_method=method,
        extraction_method=extraction_method,
        headers=headers,
        header_cells=header_cells,
        rows=rows,
        structure_score=round(assessment.table_structure_score, 3),
        acceptance="accepted" if assessment.table_acceptance_status == "accepted" else "rejected",
        reasons=[assessment.rejection_reason] if assessment.rejection_reason else [],
    )
    if not header_texts:
        table.reasons.append("no_header_row_detected")
    annotate_table(table)
    regions.insert(
        0,
        StructuredRegion(
            region_id=region_id,
            region_type="TABLE",
            text=" | ".join(headers),
            normalized_text=" | ".join(headers).lower(),
            page=page_number,
            bbox=bbox,
            children=[f"{region_id}:r{r}" for r in range(len(rows))],
            extraction_method=extraction_method,
            structural_metadata={
                "detection_method": method,
                "acceptance": table.acceptance,
                "columns": len(headers),
                "rows": len(rows),
            },
        ),
    )
    return table, regions


def _field(
    ids: _Ids,
    page_number: int,
    label_raw: str,
    value_raw: str,
    relation: str,
    label_bbox: BBox | None,
    value_bbox: BBox | None,
    evidence: str,
    extraction_method: str,
    extra_hints: list[str] | None = None,
) -> FieldCandidate:
    label_text = normalize_space(strip_label_separator(label_raw))
    reasons = [r for r in (label_rejection(label_text), value_rejection(value_raw)) if r]
    hints = list(extra_hints or [])
    if not reasons:
        hints.append("label_noun_phrase_shape")
    quality_score, quality_flags = candidate_quality(label_text, value_raw, relation)
    value_type = infer_value_type(value_raw)
    # "Registration No.  0222420149" is an identifier, not a phone number
    # that happens to have ten digits.
    if value_type in ("phone", "number") and _ID_TAIL.search(label_text) and not re.search(
        r"\b(phone|tel|fax|mobile|cell)\b", label_text, re.I
    ):
        value_type = "identifier"
    return FieldCandidate(
        quality_score=quality_score,
        quality_flags=quality_flags,
        candidate_id=ids.next("field"),
        raw_label=label_raw,
        raw_value=value_raw,
        label_text=label_text,
        value_type_hint=value_type,
        structural_relation=relation,  # type: ignore[arg-type]
        page=page_number,
        label_bbox=label_bbox,
        value_bbox=value_bbox,
        evidence_text=evidence,
        extraction_method=extraction_method,
        acceptance="rejected" if reasons else "accepted",
        reasons=reasons,
        validation_hints=hints,
    )


_LIST_ITEM = re.compile(r"^(\(?[a-z0-9]{1,3}[.)]|[•·▪●\-*])\s+\S", re.I)
_INLINE_SEP = re.compile(r"^(?P<label>[^:]{1,60}?[A-Za-z)#.])\s*:\s+(?P<value>\S.*)$")


def _inline_pairs(words: list[Word], label_words: int) -> list[tuple[list[Word], list[Word]]]:
    """Split one text run holding several "Label: value" pairs
    ("Invoice Number: INV-1001   Invoice Date: 03/14/2025"). A later word
    ending in ':' starts a new pair when the words before it form a
    label-shaped phrase; the phrase starts after the widest gap (pairs are
    usually spaced apart), else at the first capitalized word without digits."""

    pairs: list[tuple[list[Word], list[Word]]] = []
    label_start, value_start = 0, label_words
    k = value_start + 1
    while k < len(words):
        if not words[k].text.endswith(":") or k + 1 >= len(words):
            k += 1
            continue
        starts = [
            j for j in range(max(value_start + 1, k - 4), k + 1)
            if label_rejection(" ".join(w.text for w in words[j:k + 1])) is None
            and words[j].text[:1].isupper()
        ]
        if not starts:
            k += 1
            continue
        widest = max(starts, key=lambda j: words[j].x0 - words[j - 1].x1)
        gap = words[widest].x0 - words[widest - 1].x1
        if all(abs((words[j].x0 - words[j - 1].x1) - gap) < 0.5 for j in starts):
            widest = next((j for j in starts if not any(ch.isdigit() for ch in words[j].text)), widest)
        pairs.append((words[label_start:value_start], words[value_start:widest]))
        label_start, value_start = widest, k + 1
        k = value_start + 1
    pairs.append((words[label_start:value_start], words[value_start:]))
    return pairs


def _is_label_segment(seg: Segment) -> bool:
    return seg.text.rstrip().endswith(":") and label_rejection(seg.text) is None


# OCR renders printed underlines / leader dots between a label and its
# value as runs of '_', dashes or dots: "Group __ HUMANITIES".
_FILLER_PAIR = re.compile(r"^(?P<label>[^_:]{1,40}?)\s*(?:_{2,}|[—–]+|-{2,}|\.{3,}|…+)\s*(?P<value>[^\s_].*)$")
# Identifier-style label endings ("Roll No.", "Invoice #", "Customer ID",
# "Issue Date") — a shape of field captions, not a business vocabulary.
_ID_TAIL = re.compile(r"(?:\bno\.?|#|\bnumber|\bnum\.?|\bid|\bdate|\bcode|\bref\.?)$", re.I)
_VALUE_NOISE = "_|~=—–"


def _clean_label(text: str) -> str:
    # OCR punctuation variation: "Certificate No," / "No;" → "No."
    text = re.sub(r"\b(No|Ref|Acct|Inv)[,;]$", r"\1.", text.strip())
    return text.rstrip(" _—–")


def _clean_value(text: str) -> str:
    return text.strip().strip(_VALUE_NOISE).strip()


def _position_label(text: str) -> bool:
    """A run that can be a caption WITHOUT a separator: short, capitalized,
    not numeric — stricter than label_rejection alone."""

    text = _clean_label(text)
    words = text.split()
    return (
        bool(words)
        and len(words) <= 4
        and len(text) <= 32
        and text[:1].isupper()
        and label_rejection(text) is None
        and not is_numeric_value(text)
        and sum(ch.isdigit() for ch in text) <= 0.2 * len(text)
    )


def _position_value(text: str) -> bool:
    """A run that reads as a VALUE on its own: has digits, or is a short
    all-caps name/code — never a lowercase phrase or another caption."""

    text = _clean_value(text)
    words = text.split()
    letters = [ch for ch in text if ch.isalpha()]
    return (
        bool(words)
        and len(words) <= 8
        and not text.endswith(":")
        and value_rejection(text) is None
        and (any(ch.isdigit() for ch in text) or (letters and all(ch.isupper() for ch in letters) and len(words) <= 6))
    )


def _whitespace_pairs(segments: list[Segment]) -> list[tuple[Segment, Segment]]:
    """Label/value pairs separated only by whitespace ("Roll No.   516522
    Registration No.   0222420149"). Accepted when the label has an
    identifier-style ending, or when the WHOLE line alternates label,
    value, label, value — so a table row ("Bolt | EA | 0.42 | 84.00")
    never pairs up."""

    free = [s for s in segments if not s.used]
    candidates = [
        (a, b)
        for a, b in zip(free, free[1:])
        if _position_label(a.text)
        and _position_value(b.text)
        and 0 < b.x0 - a.x1 <= 200
        # Caption and value share a type size; a letterhead name beside a
        # large "INVOICE" title does not.
        and abs(a.size - b.size) <= 0.2 * max(a.size, b.size)
    ]
    # Alternation alone is only evidence with at least two pairs; a lone
    # "Brightline Office Supply Co.   INVOICE" is not a caption and value.
    alternating = (
        len(free) >= 4
        and len(free) % 2 == 0
        and all((free[i], free[i + 1]) in candidates for i in range(0, len(free), 2))
    )
    pairs: list[tuple[Segment, Segment]] = []
    taken: set[int] = set()
    for a, b in candidates:
        if id(a) in taken or id(b) in taken:
            continue
        # An identifier caption ("Roll No.", "Issue Date") takes an
        # identifier/date value — digits — never another caption such as
        # a column header ("Sr. No   SUBJECTS").
        id_pair = _ID_TAIL.search(_clean_label(a.text)) and any(ch.isdigit() for ch in b.text)
        if alternating or id_pair:
            pairs.append((a, b))
            taken.update((id(a), id(b)))
    return pairs


def _label_value_candidates(
    ids: _Ids, page_number: int, lines: list[Line], extraction_method: str
) -> list[FieldCandidate]:
    fields: list[FieldCandidate] = []

    for line in lines:
        segments = line.free_segments
        for position, seg in enumerate(segments):
            if seg.used:
                continue
            text = seg.text.strip()

            filler = _FILLER_PAIR.match(text)
            if filler and _position_label(filler.group("label")) and _clean_value(filler.group("value")):
                label = _clean_label(filler.group("label"))
                value = _clean_value(filler.group("value"))
                label_words = len(filler.group("label").split())
                fields.append(
                    _field(
                        ids, page_number, label, value, "same_line_filler",
                        _union([(w.x0, w.y0, w.x1, w.y1) for w in seg.words[:label_words]]) or seg.bbox,
                        _union([(w.x0, w.y0, w.x1, w.y1) for w in seg.words[label_words:]]) or seg.bbox,
                        text, extraction_method,
                    )
                )
                seg.used = True
                continue

            inline = _INLINE_SEP.match(text)
            if inline and not text.endswith(":") and "://" not in text:
                label, value = inline.group("label"), inline.group("value")
                label_words = min(len(label.split()), len(seg.words))
                for label_part, value_part in _inline_pairs(seg.words, label_words):
                    pair_text = " ".join(w.text for w in label_part + value_part)
                    fields.append(
                        _field(
                            ids, page_number,
                            " ".join(w.text for w in label_part).rstrip(":") + ":",
                            " ".join(w.text for w in value_part),
                            "same_line_separator",
                            _union([(w.x0, w.y0, w.x1, w.y1) for w in label_part]) or seg.bbox,
                            _union([(w.x0, w.y0, w.x1, w.y1) for w in value_part]) or seg.bbox,
                            pair_text, extraction_method,
                        )
                    )
                seg.used = True
                continue

            if text.endswith(":"):
                right = segments[position + 1] if position + 1 < len(segments) else None
                if right is not None and not right.used and not right.text.rstrip().endswith(":"):
                    fields.append(
                        _field(
                            ids, page_number, text, right.text, "left_right_separator",
                            seg.bbox, right.bbox, f"{text} {right.text}", extraction_method,
                        )
                    )
                    seg.used = right.used = True
                    continue
                below = _values_below(seg, line, lines)
                if below:
                    value = "\n".join(s.text for s in below)
                    fields.append(
                        _field(
                            ids, page_number, text, value, "label_above_value",
                            seg.bbox, _union([s.bbox for s in below]), f"{text}\n{value}",
                            extraction_method,
                        )
                    )
                    seg.used = True
                    for s in below:
                        s.used = True
                continue

            # Typography: a bold label-shaped run followed by a regular run.
            right = segments[position + 1] if position + 1 < len(segments) else None
            if (
                seg.bold
                and right is not None
                and not right.used
                and not right.bold
                and label_rejection(text) is None
                and len(text.split()) <= 4
                and "," not in text
                and abs(seg.size - right.size) <= 0.15 * max(seg.size, right.size)
                and value_rejection(right.text) is None
            ):
                fields.append(
                    _field(
                        ids, page_number, text, right.text, "left_right_typography",
                        seg.bbox, right.bbox, f"{text} {right.text}", extraction_method,
                    )
                )
                seg.used = right.used = True

        # Separator-less captions, after every explicit form above.
        for label_seg, value_seg in _whitespace_pairs(line.segments):
            label = _clean_label(label_seg.text)
            value = _clean_value(value_seg.text)
            fields.append(
                _field(
                    ids, page_number, label, value, "left_right_whitespace",
                    label_seg.bbox, value_seg.bbox, f"{label_seg.text} {value_seg.text}", extraction_method,
                )
            )
            label_seg.used = value_seg.used = True
    return fields


def _values_below(label: Segment, line: Line, lines: list[Line]) -> list[Segment]:
    """Consecutive left-aligned runs directly under a "Label:" run — e.g. a
    multi-line address under "Bill To:"."""

    def aligned(candidate_line: Line) -> Segment | None:
        return next(
            (
                s
                for s in candidate_line.free_segments
                if abs(s.x0 - label.x0) <= 12.0 or (s.x0 >= label.x0 - 2 and s.x0 <= label.x1)
            ),
            None,
        )

    window = lines[line.index + 1 : line.index + 9]
    collected: list[Segment] = []
    previous_bottom = line.y1
    for position, below_line in enumerate(window):
        if below_line.y0 - previous_bottom > 1.6 * line.height:
            break
        match = aligned(below_line)
        if match is None:
            # A line belonging only to another column (e.g. a right-hand
            # key/value block interleaved with this one) is skipped, not
            # treated as the end of the value.
            continue
        text = match.text.strip()
        if _is_label_segment(match) or _LIST_ITEM.match(text):
            # A list under a heading-like "Label:" is a list, not a value.
            break
        if _INLINE_SEP.match(text):
            # "Attn: Accounts Payable" INSIDE an address block (a plain
            # aligned line follows it) belongs to the block; a "Label:
            # value" line that starts a stack of fields ends it.
            following = next(
                (
                    s
                    for later in window[position + 1 : position + 3]
                    if later.y0 - below_line.y1 <= 1.6 * line.height
                    for s in [aligned(later)]
                    if s is not None
                ),
                None,
            )
            if not collected or following is None or _INLINE_SEP.match(following.text.strip()) or _is_label_segment(following):
                break
        collected.append(match)
        previous_bottom = below_line.y1
    return collected


def _form_widget_candidates(ids: _Ids, page, page_number: int) -> list[FieldCandidate]:
    fields = []
    try:
        widgets = list(page.widgets() or [])
    except Exception:  # noqa: BLE001
        return fields
    for widget in widgets:
        value = str(widget.field_value or "").strip()
        if not value or value.lower() in ("off", "false"):
            continue
        name = widget.field_label or widget.field_name or ""
        label = re.sub(r"(?<=[a-z])(?=[A-Z])|[_.]+", " ", name).strip()
        rect = widget.rect
        fields.append(
            _field(
                ids, page_number, label, value, "form_widget",
                None, (rect.x0, rect.y0, rect.x1, rect.y1), f"{label}: {value}", "form_widget",
            )
        )
    return fields


def _group_key_values(ids: _Ids, page_number: int, fields: list[FieldCandidate]) -> list[StructuredRegion]:
    """Stacked, left-aligned label/value pairs form one KEY_VALUE_GROUP."""

    groups: list[list[FieldCandidate]] = []
    accepted = sorted(
        (f for f in fields if f.acceptance == "accepted" and f.label_bbox),
        key=lambda f: (f.label_bbox[0], f.label_bbox[1]),
    )
    for f in accepted:
        for group in groups:
            last = group[-1]
            if abs(last.label_bbox[0] - f.label_bbox[0]) <= 4 and 0 < f.label_bbox[1] - last.label_bbox[3] <= 14:
                group.append(f)
                break
        else:
            groups.append([f])
    regions = []
    for group in groups:
        if len(group) < 2:
            continue
        region_id = ids.next("kvgroup")
        for f in group:
            f.group_id = region_id
        regions.append(
            StructuredRegion(
                region_id=region_id,
                region_type="KEY_VALUE_GROUP",
                text="\n".join(f.evidence_text for f in group),
                normalized_text="\n".join(f.evidence_text for f in group).lower(),
                page=page_number,
                bbox=_union([_union([f.label_bbox, f.value_bbox]) for f in group]),
                children=[f.candidate_id for f in group],
            )
        )
    return regions


_CONTACT_SIGNAL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}|\b[A-Z]{2}\s+\d{5}\b")


_ABBREVIATION_END = re.compile(r"(?:^|\s)(?:[A-Za-z]{1,4}\.|(?:[A-Za-z]\.){2,})$")


def _ends_like_sentence_or_label(text: str) -> bool:
    """A trailing colon/comma, or a sentence-final period — but not the
    period of an abbreviation ("Supply Co.", "Events B.V.")."""

    stripped = text.rstrip()
    if stripped.endswith((":", ",")):
        return True
    return stripped.endswith(".") and not _ABBREVIATION_END.search(stripped)


def _typography_break(upper: Segment, lower: Segment) -> bool:
    larger = upper.size >= 1.2 * lower.size
    weight = upper.bold and not lower.bold and len(upper.text.split()) <= 10
    return larger or weight


def _caps_title(text: str) -> bool:
    """OCR carries no bold/weight, so a title line is recognised by shape:
    several all-capital words, mostly letters ("HIGHER SECONDARY SCHOOL
    CERTIFICATE EXAMINATION", "ANNUAL 2005")."""

    words = text.split()
    letters = [ch for ch in text if ch.isalpha()]
    alnum = [ch for ch in text if ch.isalnum()]
    return (
        # Text on an underline ("_NOSHEEN TARIQ") fills in a form blank.
        not text.lstrip().startswith("_")
        and len(words) >= 2
        and len(letters) >= 6
        and all(ch.isupper() for ch in letters)
        and len(letters) >= 0.6 * len(alnum)
    )


def _text_regions(ids: _Ids, page_number: int, lines: list[Line], extraction_method: str) -> list[StructuredRegion]:
    """Headings, paragraphs/narrative and contact blocks from the runs no
    table or label/value claimed. Runs join a block only when they are on
    consecutive lines AND left-aligned with it, so side-by-side columns
    (a letterhead left, a title right) stay separate blocks."""

    runs = [seg for line in lines for seg in line.free_segments]
    if not runs:
        return []
    body_size = statistics.median(s.size for s in runs)
    line_of = {id(seg): line for line in lines for seg in line.segments}

    blocks: list[list[Segment]] = []
    for seg in runs:
        line = line_of[id(seg)]
        target = None
        for block in reversed(blocks[-12:]):
            last = block[-1]
            last_line = line_of[id(last)]
            if (
                last_line.index < line.index
                and line.y0 - last_line.y1 <= 1.2 * last_line.height
                and abs(seg.x0 - block[0].x0) <= 12.0
                # A typography change (a larger or bold name line above
                # regular address lines) starts a new block.
                and not (len(block) == 1 and _typography_break(last, seg))
            ):
                target = block
                break
        if target is None:
            blocks.append([seg])
        else:
            target.append(seg)

    regions: list[StructuredRegion] = []
    for block in blocks:
        text = "\n".join(s.text for s in block)
        words = len(text.split())
        bbox = _union([s.bbox for s in block])
        size = statistics.median(s.size for s in block)
        if (
            len(block) == 1
            and words <= 10
            and not _ends_like_sentence_or_label(text)
            and (block[0].bold or size >= 1.2 * body_size or (extraction_method == "ocr" and _caps_title(text)))
            and re.search(r"[A-Za-z]", text)
            # "grade" set in a larger OCR box is still a lowercase word, not a title.
            and not text[:1].islower()
            # An email/URL run can look "large" to OCR ('@', descenders)
            # but is contact data, never a heading.
            and not re.search(r"@|www\.|https?://", text)
        ):
            kind = "HEADING"
        elif _CONTACT_SIGNAL.search(text) and len(block) <= 8 and words <= 60:
            kind = "CONTACT_BLOCK"
        elif words >= 25:
            kind = "NARRATIVE"
        else:
            kind = "PARAGRAPH"
        regions.append(
            StructuredRegion(
                region_id=ids.next(kind.lower()),
                region_type=kind,  # type: ignore[arg-type]
                text=text if kind != "NARRATIVE" else text[:600],
                normalized_text=normalize_space(text).lower()[:600],
                page=page_number,
                bbox=bbox,
                extraction_method=extraction_method,
                structural_metadata={
                    "lines": len(block),
                    "words": words,
                    "font_size": round(size, 1),
                    "bold": all(s.bold for s in block),
                },
            )
        )
    return regions


def extract_page_structure(
    *,
    page_number: int,
    words: list[Word],
    extraction_method: str,
    fitz_page=None,
) -> PageStructure:
    ids = _Ids(page_number)
    result = PageStructure()
    if not words:
        return result
    lines = build_lines(words)
    page_text = "\n".join(" ".join(s.text for s in line.segments) for line in lines)

    # 1. Ruled tables (native only — OCR has no vector ruling lines). The
    # table finder is the expensive step, so it only runs where the words
    # already show multi-column structure.
    multi_column_lines = sum(1 for line in lines if len(line.segments) >= 3)
    if fitz_page is not None and extraction_method == "native" and multi_column_lines >= 3:
        for bbox, data, cell_boxes, header_names in _ruled_tables(fitz_page, page_number):
            texts = [[normalize_space(str(c or "")) for c in row] for row in data]
            boxes = [[tuple(b) if b else None for b in row] for row in cell_boxes]
            header, body = texts[0], texts[1:]
            header_ok = all(h and not is_numeric_value(h) for h in header)
            table, regions = _table_from_grid(
                ids, page_number, "pdf_ruling_lines", extraction_method,
                header if header_ok else None,
                boxes[0] if header_ok else [],
                body if header_ok else texts,
                boxes[1:] if header_ok else boxes,
                page_text, tuple(bbox),
            )
            result.tables.append(table)
            result.regions.extend(regions)
            if table.acceptance == "accepted":
                x0, y0, x1, y1 = bbox
                for line in lines:
                    for seg in line.segments:
                        sx0, sy0, sx1, sy1 = seg.bbox
                        if sx0 >= x0 - 1 and sx1 <= x1 + 1 and sy0 >= y0 - 1 and sy1 <= y1 + 1:
                            seg.used = True

    # 2. Label/value pairs claim their segments before column alignment,
    # so a stack of "Label: value" lines is never mistaken for a table.
    widget_fields = _form_widget_candidates(ids, fitz_page, page_number) if fitz_page is not None else []
    fields = _label_value_candidates(ids, page_number, lines, extraction_method)
    fields.extend(widget_fields)

    # 3. Column-aligned tables from the remaining runs.
    for bands, grid, members in _alignment_tables(lines):
        header_is_first = _is_header_row(grid[0], grid[1:])
        header_cells = grid[0] if header_is_first else None
        body = grid[1:] if header_is_first else grid
        table, regions = _table_from_grid(
            ids, page_number, "pdf_column_alignment", extraction_method,
            [_cell_text(c) for c in header_cells] if header_cells else None,
            [_union([s.bbox for s in c]) for c in header_cells] if header_cells else [],
            [[_cell_text(c) for c in row] for row in body],
            [[_union([s.bbox for s in c]) for c in row] for row in body],
            page_text,
            _union([s.bbox for line in members for s in line.free_segments]),
        )
        result.tables.append(table)
        result.regions.extend(regions)
        if table.acceptance == "accepted":
            for line in members:
                for seg in line.free_segments:
                    seg.used = True

    for f in fields:
        result.regions.append(
            StructuredRegion(
                region_id=f"{f.candidate_id}:region",
                region_type="FORM_FIELD" if f.structural_relation == "form_widget" else "LABEL_VALUE",
                text=f.evidence_text,
                normalized_text=normalize_space(f.evidence_text).lower(),
                page=page_number,
                bbox=_union([f.label_bbox, f.value_bbox]),
                extraction_method=extraction_method,
                structural_metadata={"acceptance": f.acceptance, "relation": f.structural_relation},
            )
        )
        f.source_region_ids.append(f"{f.candidate_id}:region")
    result.fields = fields
    result.regions.extend(_group_key_values(ids, page_number, fields))
    result.regions.extend(_text_regions(ids, page_number, lines, extraction_method))
    return result
