"""Reading-order reconstruction: the user-facing transcript of a PDF or
image page, rebuilt from positioned words (native PDF text or OCR).

    words (page-space boxes)
      → lines            skew-aware clustering (pdf_structure.build_lines)
      → runs             segments within a line (word-gap split)
      → regions          recursive cuts: a vertical gutter that is NOT a
                         row-aligned grid splits columns (read one column
                         fully before the next); otherwise horizontal gaps
                         split bands top → bottom
      → blocks           consecutive lines of a region merged into
                         paragraphs; accepted tables rendered as tables;
                         single short title-shaped lines as headings

Row-aligned layouts — "Roll No. 516522   Registration No. 0222420149",
"Subtotal ....... $605.20" — are grids, not columns: every left line has a
partner at the same height on the right, so they are read row by row. Two
columns of prose have independent line positions, so they are cut.

Every line keeps its contributing words' page-space boxes, so a transcript
line can highlight its source region. Nothing here sorts words globally by
(y, x).
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from app.source_structure.models import BBox, TableCandidate
from app.source_structure.pdf_structure import Line, Segment, Word, build_lines

# Fraction of a candidate gutter's left-side lines that must have a partner
# line at the same height on the right for the pair to count as a grid
# (label | value, totals) rather than two text columns.
_ROW_ALIGNED = 0.6


@dataclass
class _Run:
    segment: Segment
    line: Line

    @property
    def x0(self) -> float:
        return self.segment.x0

    @property
    def x1(self) -> float:
        return self.segment.x1

    @property
    def y0(self) -> float:
        return min(w.row_y0 for w in self.segment.words)

    @property
    def y1(self) -> float:
        return max(w.row_y1 for w in self.segment.words)


@dataclass
class TranscriptLine:
    text: str
    bbox: BBox
    words: list[dict] = field(default_factory=list)


@dataclass
class TranscriptBlock:
    kind: str  # heading | paragraph | table
    lines: list[TranscriptLine] = field(default_factory=list)
    table_headers: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    bbox: BBox | None = None

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "text": "\n".join(line.text for line in self.lines),
            "bbox": list(self.bbox) if self.bbox else None,
            "lines": [
                {"text": line.text, "bbox": list(line.bbox), "words": line.words} for line in self.lines
            ],
            "table": (
                {"headers": self.table_headers, "rows": self.table_rows} if self.kind == "table" else None
            ),
        }


def _union(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _row_aligned(left: list[_Run], right: list[_Run]) -> bool:
    if not left or not right:
        return False
    partnered = sum(
        1
        for a in left
        if any(min(a.y1, b.y1) - max(a.y0, b.y0) > 0.4 * min(a.y1 - a.y0, b.y1 - b.y0) for b in right)
    )
    return partnered >= _ROW_ALIGNED * len(left)


def _vertical_cut(runs: list[_Run], gutter: float) -> tuple[list[_Run], list[_Run]] | None:
    """Split at the widest empty vertical strip spanning all runs, unless
    the two sides form a row-aligned grid."""

    spans = sorted((r.x0, r.x1) for r in runs)
    best: tuple[float, float] | None = None
    reach = spans[0][1]
    for x0, x1 in spans[1:]:
        if x0 - reach >= gutter and (best is None or x0 - reach > best[1] - best[0]):
            best = (reach, x0)
        reach = max(reach, x1)
    if best is None:
        return None
    middle = (best[0] + best[1]) / 2
    left = [r for r in runs if r.x1 <= middle]
    right = [r for r in runs if r.x0 >= middle]
    # A column spans several lines; one trailing word ("… as a  REGULAR")
    # does not make the space before it a gutter.
    if len({r.line.index for r in left}) < 2 or len({r.line.index for r in right}) < 2:
        return None
    # A grid (captions | values, totals) has row-aligned sides AND a gutter
    # wide relative to its short runs. Prose columns may share line heights
    # too, but their gutter is narrow next to full-width lines — cut those.
    gutter_width = best[1] - best[0]
    narrow_runs = gutter_width >= 0.6 * statistics.median(r.x1 - r.x0 for r in left)
    # Captions are a few words; lines of running text are sentences.
    short_runs = statistics.median(len(r.segment.words) for r in left) <= 4
    # A side with its own caption ("Customer:" over an address) is its own
    # block, not the values of the rows beside it.
    own_caption = any(r.segment.text.rstrip().endswith(":") for r in right)
    if narrow_runs and short_runs and not own_caption and (_row_aligned(left, right) or _row_aligned(right, left)):
        return None
    return left, right


def _horizontal_cut(runs: list[_Run], gap: float) -> tuple[list[list[_Run]], float] | None:
    """Bands separated by full-width vertical space, and the widest such gap."""

    ordered = sorted(runs, key=lambda r: r.y0)
    bands: list[list[_Run]] = [[ordered[0]]]
    bottom = ordered[0].y1
    widest = 0.0
    for run in ordered[1:]:
        if run.y0 - bottom >= gap:
            widest = max(widest, run.y0 - bottom)
            bands.append([run])
        else:
            bands[-1].append(run)
        bottom = max(bottom, run.y1)
    return (bands, widest) if len(bands) > 1 else None


def _order(runs: list[_Run], gutter: float, gap: float, depth: int = 0) -> list[list[_Run]]:
    """Runs grouped into regions, regions in reading order."""

    if len(runs) <= 1 or depth > 40:
        return [runs]
    # Section breaks (≥ two lines of space across the full width) separate
    # regions before columns are looked for, so a column above and a grid
    # below are never judged as one region. Only those large gaps split
    # here; ordinary line spacing is left for after the column search.
    sections = _horizontal_cut(runs, 2 * gap)
    if sections:
        return [region for band in sections[0] for region in _order(band, gutter, gap, depth + 1)]
    split = _vertical_cut(runs, gutter)
    if split:
        return [region for side in split for region in _order(side, gutter, gap, depth + 1)]
    horizontal = _horizontal_cut(runs, gap)
    if horizontal:
        return [region for band in horizontal[0] for region in _order(band, gutter, gap, depth + 1)]
    return [runs]


def _region_lines(runs: list[_Run]) -> list[list[_Run]]:
    """A region's runs as visual lines (by source line), top to bottom,
    each line's runs left to right."""

    by_line: dict[int, list[_Run]] = {}
    for run in runs:
        by_line.setdefault(run.line.index, []).append(run)
    lines = [sorted(group, key=lambda r: r.x0) for group in by_line.values()]
    return sorted(lines, key=lambda group: min(r.y0 for r in group))


def _readable(text: str) -> str:
    """OCR'd underline fill between or around words ("Group __ HUMANITIES",
    "_422005") is layout, not content. Display only — words keep raw text."""

    text = re.sub(r"\s+_{2,}\s+", " ", text)
    return text.strip().strip("_").strip()


def _transcript_line(group: list[_Run]) -> TranscriptLine:
    words = [w for run in group for w in run.segment.words]
    # Runs of one line are joined with a wide space so a grid row still
    # reads as "Label   value", while each run keeps its own words.
    text = "   ".join(filter(None, (_readable(run.segment.text) for run in group)))
    return TranscriptLine(
        text=text,
        bbox=_union([(w.x0, w.y0, w.x1, w.y1) for w in words]),
        words=[{"text": w.text, "bbox": [round(w.x0, 2), round(w.y0, 2), round(w.x1, 2), round(w.y1, 2)]} for w in words],
    )


def _is_heading(line: TranscriptLine, group: list[_Run], body_size: float) -> bool:
    text = line.text.strip()
    letters = [ch for ch in text if ch.isalpha()]
    if len(group) != 1 or not letters or len(text.split()) > 10 or text[:1].islower():
        return False
    if text.endswith((".", ",", ";", ":")):
        return False
    size = statistics.median(w.size for w in group[0].segment.words)
    caps = (
        len(text.split()) >= 2
        and len(letters) >= 4
        and all(ch.isupper() for ch in letters)
        and not text.lstrip().startswith("_")
    )
    return group[0].segment.bold or size >= 1.2 * body_size or caps


def _table_block(table: TableCandidate) -> TranscriptBlock:
    rows = [[cell.text for cell in row] for row in table.rows]
    has_header = bool(table.header_cells)
    boxes = [c.bbox for row in table.rows for c in row if c.bbox]
    return TranscriptBlock(
        kind="table",
        table_headers=list(table.headers) if has_header else [],
        table_rows=rows,
        bbox=table.bbox or (_union(boxes) if boxes else None),
        lines=[
            TranscriptLine(
                text=" | ".join(c.text for c in row if c.text),
                bbox=_union([c.bbox for c in row if c.bbox]) if any(c.bbox for c in row) else (0, 0, 0, 0),
            )
            for row in table.rows
        ],
    )


def _inside(run: _Run, bbox: BBox) -> bool:
    x0, y0, x1, y1 = run.segment.bbox
    return x0 >= bbox[0] - 2 and x1 <= bbox[2] + 2 and y0 >= bbox[1] - 2 and y1 <= bbox[3] + 2


def reconstruct_page(words: list[Word], tables: list[TableCandidate] | None = None) -> list[TranscriptBlock]:
    """Transcript blocks for one page, in reading order."""

    if not words:
        return []
    lines = build_lines(words)
    runs = [_Run(seg, line) for line in lines for seg in line.segments]
    heights = [r.y1 - r.y0 for r in runs if r.y1 > r.y0]
    line_height = statistics.median(heights) if heights else 10.0
    body_size = statistics.median(w.size for w in words)

    # Accepted tables are emitted as tables where their first run falls in
    # the reading order; their runs don't also appear as text.
    table_of: dict[int, TableCandidate] = {}
    accepted = [t for t in tables or [] if t.acceptance == "accepted" and t.bbox]
    for run in runs:
        for table in accepted:
            if _inside(run, table.bbox):
                table_of[id(run)] = table
                break

    regions = _order(runs, gutter=max(12.0, 1.5 * line_height), gap=max(6.0, 0.9 * line_height))
    blocks: list[TranscriptBlock] = []
    emitted_tables: set[str] = set()
    for region in regions:
        paragraph: TranscriptBlock | None = None
        previous_bottom: float | None = None
        for group in _region_lines(region):
            tabled = [r for r in group if id(r) in table_of]
            if tabled:
                table = table_of[id(tabled[0])]
                if table.candidate_id not in emitted_tables:
                    emitted_tables.add(table.candidate_id)
                    blocks.append(_table_block(table))
                paragraph = None
                group = [r for r in group if id(r) not in table_of]
                if not group:
                    continue
            line = _transcript_line(group)
            top = min(r.y0 for r in group)
            if _is_heading(line, group, body_size):
                blocks.append(TranscriptBlock(kind="heading", lines=[line], bbox=line.bbox))
                paragraph, previous_bottom = None, max(r.y1 for r in group)
                continue
            # A caption line ("Customer:") keeps the block directly under it.
            after_caption = (
                paragraph is not None
                and paragraph.lines[-1].text.rstrip().endswith(":")
                and previous_bottom is not None
                and top - previous_bottom <= 2 * line_height
            )
            starts_new = not after_caption and (
                paragraph is None
                or previous_bottom is None
                or top - previous_bottom > 0.8 * line_height
                # A grid row (several runs) stands on its own line.
                or len(group) > 1
                or len(paragraph.lines[-1].text.split("   ")) > 1
            )
            if starts_new:
                paragraph = TranscriptBlock(kind="paragraph", lines=[line], bbox=line.bbox)
                blocks.append(paragraph)
            else:
                paragraph.lines.append(line)
                paragraph.bbox = _union([paragraph.bbox, line.bbox])
            previous_bottom = max(r.y1 for r in group)
    return blocks


def plain_text(blocks: list[TranscriptBlock]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.kind == "table":
            rows = ([block.table_headers] if block.table_headers else []) + block.table_rows
            parts.append("\n".join(" | ".join(cell for cell in row) for row in rows))
        else:
            parts.append("\n".join(line.text for line in block.lines))
    return "\n\n".join(parts)
