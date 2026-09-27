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

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


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
        words.append(Word(text, x0, y0, x1, y1, size, bold))
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
    return words


# --- lines and segments ----------------------------------------------------


def build_lines(words: list[Word]) -> list[Line]:
    lines: list[Line] = []
    for word in sorted(words, key=lambda w: (w.cy, w.x0)):
        height = max(1.0, word.y1 - word.y0)
        target = None
        for line in reversed(lines[-6:]):
            overlap = min(line.y1, word.y1) - max(line.y0, word.y0)
            if overlap >= 0.5 * min(line.height, height):
                target = line
                break
        if target is None:
            target = Line(index=len(lines))
            lines.append(target)
        target.words.append(word)

    lines.sort(key=lambda l: (l.y0, min(w.x0 for w in l.words)))
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
            if len(line.free_segments) >= 2:
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
            tables.append((bands, grid, members))
            i = j
        else:
            i += 1
    return tables


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
    return FieldCandidate(
        quality_score=quality_score,
        quality_flags=quality_flags,
        candidate_id=ids.next("field"),
        raw_label=label_raw,
        raw_value=value_raw,
        label_text=label_text,
        value_type_hint=infer_value_type(value_raw),
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


def _is_label_segment(seg: Segment) -> bool:
    return seg.text.rstrip().endswith(":") and label_rejection(seg.text) is None


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

            inline = _INLINE_SEP.match(text)
            if inline and not text.endswith(":") and "://" not in text:
                label, value = inline.group("label"), inline.group("value")
                label_words = min(len(label.split()), len(seg.words))
                fields.append(
                    _field(
                        ids, page_number, label + ":", value, "same_line_separator",
                        _union([(w.x0, w.y0, w.x1, w.y1) for w in seg.words[:label_words]]) or seg.bbox,
                        _union([(w.x0, w.y0, w.x1, w.y1) for w in seg.words[label_words:]]) or seg.bbox,
                        text, extraction_method,
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
    return fields


def _values_below(label: Segment, line: Line, lines: list[Line]) -> list[Segment]:
    """Consecutive left-aligned runs directly under a "Label:" run — e.g. a
    multi-line address under "Bill To:"."""

    collected: list[Segment] = []
    previous_bottom = line.y1
    for below_line in lines[line.index + 1 : line.index + 8]:
        if below_line.y0 - previous_bottom > 1.6 * line.height:
            break
        match = next(
            (
                s
                for s in below_line.free_segments
                if abs(s.x0 - label.x0) <= 12.0 or (s.x0 >= label.x0 - 2 and s.x0 <= label.x1)
            ),
            None,
        )
        if match is None:
            # A line belonging only to another column (e.g. a right-hand
            # key/value block interleaved with this one) is skipped, not
            # treated as the end of the value.
            continue
        if (
            _is_label_segment(match)
            or _INLINE_SEP.match(match.text.strip())
            or _LIST_ITEM.match(match.text.strip())
        ):
            # A list under a heading-like "Label:" is a list, not a value.
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
            and not text.rstrip().endswith((":", ".", ","))
            and (block[0].bold or size >= 1.2 * body_size)
            and re.search(r"[A-Za-z]", text)
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
