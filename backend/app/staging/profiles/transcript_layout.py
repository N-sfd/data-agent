"""Logical reconstruction of an academic record from positioned words.

The schema-neutral structure (app/source_structure/) describes PHYSICAL
layout: ruled cells, runs, label/value candidates. A transcript's meaning
often spans several physical pieces — "Date | of | Birth | : | 15 May 2001"
in ruled boxes, a degree name wrapped onto a second line, a course title
continued under its row. This module rebuilds LOGICAL units from the page's
lines (pdf_structure.build_lines over native or OCR words):

    lines ─┬─ course tables   a header line whose captions are course-table
           │                  vocabulary anchors the columns; rows below are
           │                  assigned by geometry; term/grade group lines,
           │                  wrapped cells and total/GPA rows are recognised
           ├─ sections        "Grading Scale", "Graduation Requirements", …
           │                  and the lines beneath them
           ├─ label/value     "Label: value", "Label : value", a known label
           │                  beside or above its value, wrapped values
           ├─ letterhead      institution name / address / contacts
           └─ certification   statements and signatory captions

Every logical value keeps the physical fragments (with word boxes and OCR
confidence) it was built from; nothing is invented and no geometry is
fabricated. Vocabulary lives in transcript_vocabulary.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from app.source_structure.pdf_structure import Line, Segment, Word, build_lines
from app.staging.profiles import transcript_vocabulary as V


# --- fragments -------------------------------------------------------------------------


@dataclass
class Fragment:
    """One physical piece of source text: consecutive words of one line."""

    words: list[Word]
    page: int
    line_index: int

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def x1(self) -> float:
        return max(w.x1 for w in self.words)

    @property
    def y0(self) -> float:
        return min(w.y0 for w in self.words)

    @property
    def y1(self) -> float:
        return max(w.y1 for w in self.words)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


def union_bbox(fragments: list[Fragment]) -> tuple[float, float, float, float] | None:
    boxes = [f.bbox for f in fragments if f.words]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def fragments_text(fragments: list[Fragment]) -> str:
    return " ".join(f.text for f in fragments if f.words).strip()


def evidence_of(fragments: list[Fragment]) -> str:
    """Literal source text of the fragments: one line per source line, runs
    of a line separated as they are on the page."""

    by_line: dict[tuple[int, int], list[Fragment]] = {}
    for fragment in fragments:
        if fragment.words:
            by_line.setdefault((fragment.page, fragment.line_index), []).append(fragment)
    lines = []
    for key in sorted(by_line, key=lambda k: (k[0], min(f.y0 for f in by_line[k]))):
        lines.append("   ".join(f.text for f in sorted(by_line[key], key=lambda f: f.x0)))
    return "\n".join(lines)


def _seg(seg: Segment, page: int) -> Fragment:
    return Fragment(list(seg.words), page, seg.line_index)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _clean_value(text: str) -> str:
    text = re.sub(r"^[\s:=|_·•*]+", "", text)
    text = re.sub(r"[\s|_·•]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_label(text: str) -> str:
    return re.sub(r"[\s:=|_]+$", "", re.sub(r"^[\s|_*•·]+", "", text)).strip()


# --- logical units ---------------------------------------------------------------------


@dataclass
class Pair:
    label_frags: list[Fragment]
    value_frags: list[Fragment]
    page: int
    relation: str  # separator | known_label | label_above | letterhead | shape
    extra_frags: list[Fragment] = field(default_factory=list)  # separators, for evidence only
    context: str | None = None  # student | institution | program
    scope: str | None = None  # the course-table group a summary value belongs to
    in_letterhead: bool = False
    # Letterhead values have no printed label; the profile names them from
    # the value's shape (e.g. an institution's phone number).
    shape_label: str | None = None

    @property
    def label(self) -> str:
        return self.shape_label or _clean_label(fragments_text(self.label_frags))

    @property
    def value(self) -> str:
        return _clean_value(fragments_text(self.value_frags))

    @property
    def evidence(self) -> str:
        return evidence_of(self.label_frags + self.extra_frags + self.value_frags)


@dataclass
class Column:
    role: str | None
    header: str | None  # printed caption, None when not printed / illegible
    display: str | None
    x0: float
    x1: float
    header_frags: list[Fragment] = field(default_factory=list)
    inferred: bool = False  # role read from the column's values, not a caption

    @property
    def center(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class CourseRow:
    cells: dict[int, list[Fragment]]
    group: dict[str, str]
    group_frags: dict[str, list[Fragment]]
    page: int
    line_indices: list[int]
    row_frags: list[Fragment] = field(default_factory=list)


@dataclass
class CourseTable:
    columns: list[Column]
    rows: list[CourseRow]
    page: int
    header_line: int


@dataclass
class SummaryItem:
    label: str  # source wording (row label and/or column caption)
    label_frags: list[Fragment]
    value_frags: list[Fragment]
    page: int
    scope: str | None
    evidence: str

    @property
    def value(self) -> str:
        return _clean_value(fragments_text(self.value_frags))


@dataclass
class SectionEntry:
    category: str
    entry_label: str  # display label when the line has no label of its own
    label: str | None  # printed label, if the line has one
    label_frags: list[Fragment]
    value_frags: list[Fragment]
    page: int
    heading: str
    # Caption-qualified reading of a row under a caption line
    # ("Credit Req'd: 20.00 · Completed: 5.00"); None = the plain value.
    display_value: str | None = None

    @property
    def value(self) -> str:
        return self.display_value or _clean_value(fragments_text(self.value_frags))

    @property
    def evidence(self) -> str:
        return evidence_of(self.label_frags + self.value_frags)


@dataclass
class TranscriptLayout:
    pairs: list[Pair] = field(default_factory=list)
    tables: list[CourseTable] = field(default_factory=list)
    summary: list[SummaryItem] = field(default_factory=list)
    entries: list[SectionEntry] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)


# --- page model ----------------------------------------------------------------------


@dataclass
class _Page:
    number: int
    lines: list[Line]
    line_height: float
    width: float
    used: set[int] = field(default_factory=set)  # id(Segment)
    # Line index → scope of a course-table group, for pairs printed inside
    # a table's body ("Credit Attempted: 10.00" under one term).
    line_scope: dict[int, str] = field(default_factory=dict)
    # (y, kind) of lines that end a heading context (table headers, sections).
    barriers: list[float] = field(default_factory=list)
    contexts: list[tuple[float, float, float, str]] = field(default_factory=list)  # y, x0, x1, kind
    letterhead_bottom: float | None = None

    def free(self, line: Line) -> list[Segment]:
        return [s for s in line.segments if id(s) not in self.used]

    def use(self, *segments: Segment) -> None:
        self.used.update(id(s) for s in segments)


def _page(number: int, words: list[Word]) -> _Page:
    lines = build_lines(words)
    heights = [l.height for l in lines if l.words]
    width = max((w.x1 for w in words), default=612.0)
    return _Page(number, lines, statistics.median(heights) if heights else 10.0, width)


# --- course tables ---------------------------------------------------------------------


def _phrase_columns(segment: Segment, page: int) -> list[Column]:
    """A header run split into captions: longest vocabulary phrases first;
    leftover words stay as unrecognised captions (or illegible ones)."""

    words = segment.words
    columns: list[Column] = []
    pending: list[Word] = []

    def flush() -> None:
        if not pending:
            return
        text = " ".join(w.text for w in pending)
        legible = sum(ch.isalpha() for ch in text) >= 3
        columns.append(
            Column(
                role=None,
                header=_clean_label(text) if legible else None,
                display=None,
                x0=min(w.x0 for w in pending),
                x1=max(w.x1 for w in pending),
                header_frags=[Fragment(list(pending), page, segment.line_index)],
            )
        )
        pending.clear()

    i = 0
    while i < len(words):
        for n in (4, 3, 2, 1):
            if i + n > len(words):
                continue
            chunk = words[i : i + n]
            role = V.column_role(" ".join(w.text for w in chunk))
            if role:
                flush()
                columns.append(
                    Column(
                        role=role.role,
                        header=_clean_label(" ".join(w.text for w in chunk)),
                        display=role.display_label,
                        x0=min(w.x0 for w in chunk),
                        x1=max(w.x1 for w in chunk),
                        header_frags=[Fragment(list(chunk), page, segment.line_index)],
                    )
                )
                i += n
                break
        else:
            pending.append(words[i])
            i += 1
    flush()
    return columns


def _header_columns(line: Line, page: _Page) -> list[Column] | None:
    segments = page.free(line)
    if not segments or any(w.text.rstrip().endswith(":") and w is not s.words[-1] for s in segments for w in s.words):
        return None
    columns = [c for s in segments for c in _phrase_columns(s, page.number)]
    known = [c for c in columns if c.role]
    roles = {c.role for c in known}
    if len(roles) < 2 or not (roles & V.ITEM_ROLES) or not (roles & (V.RESULT_ROLES | V.CONTEXT_ROLES)):
        return None
    alpha = [w for s in segments for w in s.words if sum(ch.isalpha() for ch in w.text) >= 2]
    matched = sum(len(f.words) for c in known for f in c.header_frags)
    if not alpha or matched / len(alpha) < 0.7:
        return None
    # Captions directly under a section heading ("CREDIT SUMMARY" over
    # "Subject Area | Credit Req'd | Completed") belong to that section.
    above = page.lines[line.index - 1] if line.index > 0 else None
    if (
        above is not None
        and line.y0 - above.y1 < 1.5 * page.line_height
        and any(_section_heading(s) for s in above.segments)
    ):
        return None
    # Data lines never carry captions only: a header has no numbers.
    if any(re.search(r"\d", c.header or "") for c in known):
        return None
    return sorted(columns, key=lambda c: c.x0)


def _merge_stacked_caption(columns: list[Column], above: Line, header: Line, page: _Page) -> bool:
    """'CONTACT' printed above 'HOURS' is one caption."""

    segments = page.free(above)
    if not segments or header.y0 - above.y1 > 0.8 * page.line_height:
        return False
    if any(_section_heading(s) or V.TITLE_WORDS.search(s.text) for s in segments):
        return False
    for segment in segments:
        words = segment.text.split()
        if len(words) > 2 or not all(re.fullmatch(r"[A-Za-z.()]+", w) for w in words):
            return False
    targets = []
    for segment in segments:
        best = max(columns, key=lambda c: _overlap(segment.x0, segment.x1, c.x0 - 4, c.x1 + 4))
        if _overlap(segment.x0, segment.x1, best.x0 - 4, best.x1 + 4) <= 0:
            return False
        targets.append((segment, best))
    for segment, column in targets:
        header = f"{segment.text} {column.header or ''}".strip()
        role = V.column_role(header)
        column.header = _clean_label(header)
        if role:
            column.role, column.display = role.role, role.display_label
        column.header_frags.insert(0, _seg(segment, page.number))
        column.x0, column.x1 = min(column.x0, segment.x0), max(column.x1, segment.x1)
    page.use(*segments)
    return True


def _panels(columns: list[Column]) -> list[list[Column]]:
    """Side-by-side tables share one header line: a caption role repeating
    starts the next panel."""

    panels: list[list[Column]] = [[]]
    seen: set[str] = set()
    for column in columns:
        if column.role and column.role in seen:
            panels.append([])
            seen = set()
        panels[-1].append(column)
        if column.role:
            seen.add(column.role)
    return [p for p in panels if p]


def _group_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    year = V.ACADEMIC_YEAR.search(text)
    if year:
        values["academic_year"] = year.group(0).strip()
    level = V.GRADE_LEVEL.search(text)
    if level:
        values["grade_level"] = level.group(0).strip()
    term = V.TERM.search(text)
    if term:
        values["term"] = term.group(0).strip()
    return values


def _is_group_line(segments: list[Segment]) -> dict[str, str] | None:
    if not segments or len(segments) > 3:
        return None
    text = " ".join(s.text for s in segments)
    if len(text.split()) > 7 or V.SCORE.search(text):
        return None
    values = _group_values(text)
    if not values:
        return None
    # Everything on the line is part of a term/year/grade caption.
    leftover = text
    for value in values.values():
        leftover = leftover.replace(value, " ")
    leftover = re.sub(r"[^A-Za-z]", "", leftover)
    if len(leftover) > 6:
        return None
    return values


def _column_for(fragment: Fragment, columns: list[Column]) -> int | None:
    best, best_overlap = None, 0.0
    for index, column in enumerate(columns):
        overlap = _overlap(fragment.x0, fragment.x1, column.x0 - 3, column.x1 + 3)
        if overlap > best_overlap:
            best, best_overlap = index, overlap
    if best is not None:
        return best
    nearest, distance = None, 24.0
    for index, column in enumerate(columns):
        gap = max(column.x0 - fragment.x1, fragment.x0 - column.x1)
        if gap <= distance:
            nearest, distance = index, gap
    return nearest


def _infer_role(values: list[str], has_title: bool) -> tuple[str | None, str | None]:
    values = [v.strip() for v in values if v.strip()]
    if not values:
        return None, None

    def most(test) -> bool:
        # A clear majority, so one OCR-misread value ("8" for "B") does not
        # hide what the column holds; the misread cell itself stays Needs
        # Review on its own evidence.
        return sum(1 for v in values if test(v)) >= max(1, 0.7 * len(values))

    if most(lambda v: V.ACADEMIC_YEAR.fullmatch(v.replace(" ", "")) or V.ACADEMIC_YEAR.fullmatch(v)):
        return "academic_year", "Academic Year"
    if most(V.TERM.fullmatch):
        return "term", "Term"
    if most(V.LETTER_GRADE.match):
        return "grade", "Grade"
    if most(V.SCORE.match):
        return "score", "Marks"
    wordy = [v for v in values if sum(ch.isalpha() for ch in v) >= 3 and not re.search(r"\d{2,}", v)]
    if not has_title and len(wordy) >= 0.7 * len(values):
        return "title", "Course Title"
    return None, None


def _pair_line(segments: list[Segment]) -> bool:
    return any(re.search(r"[A-Za-z]{2}[^:]*:\s*\S", s.text) or s.text.rstrip().endswith(":") for s in segments)


def _data_like(segments: list[Segment], panel: list[Column]) -> bool:
    """A course row: at least two cells, one of them under a course
    (code/title) caption."""

    cells = {}
    for segment in segments:
        if _pair_line([segment]):
            continue  # a labelled value, not a table cell
        index = _column_for(_seg(segment, 0), panel)
        if index is not None:
            cells[index] = segment
    roles = {panel[i].role for i in cells}
    return len(cells) >= 2 and bool(roles & V.ITEM_ROLES)


def _context_line(segments: list[Segment], panel: list[Column], first_panel: bool) -> bool:
    """A line naming a sub-section of the record (a school attended, a
    program) rather than a course: its leading run starts left of the
    first column, or spreads across several columns, and is prose."""

    lead = min(segments, key=lambda s: s.x0)
    words = lead.text.split()
    if len(words) < 3 or re.fullmatch(r"[\d.\s/]+", lead.text) or _pair_line([lead]):
        return False
    spans = sum(1 for c in panel if _overlap(lead.x0, lead.x1, c.x0, c.x1) > 0)
    starts_left = first_panel and lead.x0 < panel[0].x0 - 15
    return (starts_left and spans >= 1) or spans >= 3 or (spans >= 2 and len(segments) == 1)


def _parse_table(page: _Page, header_index: int, columns: list[Column], layout: TranscriptLayout) -> list[CourseTable]:
    lines = page.lines
    header = lines[header_index]
    if header_index > 0:
        _merge_stacked_caption(columns, lines[header_index - 1], header, page)
    page.use(*page.free(header))
    page.barriers.append(header.y0)
    panels = _panels(columns)
    bounds = []
    for p, panel in enumerate(panels):
        left = -1e9 if p == 0 else panel[0].x0 - 10
        right = panels[p + 1][0].x0 - 10 if p + 1 < len(panels) else 1e9
        bounds.append((left, right))

    def in_panel(segment: Segment, p: int) -> bool:
        center = (segment.x0 + segment.x1) / 2
        return bounds[p][0] <= center < bounds[p][1]

    # A term/year caption just above the header opens the first group.
    groups: list[dict[str, str]] = [{} for _ in panels]
    group_frags: list[dict[str, list[Fragment]]] = [{} for _ in panels]
    for back in (1, 2):
        index = header_index - back
        if index < 0 or header.y0 - lines[index].y1 > 2.5 * page.line_height:
            break
        above = lines[index]
        found = False
        for p in range(len(panels)):
            segments = [s for s in above.segments if in_panel(s, p)]
            values = _is_group_line(segments)
            if values:
                groups[p] = dict(values)
                group_frags[p] = {k: [_seg(s, page.number) for s in segments] for k in values}
                page.use(*segments)
                found = True
        if found:
            break

    rows: list[list[CourseRow]] = [[] for _ in panels]
    unheaded: list[list[tuple[CourseRow, Fragment]]] = [[] for _ in panels]
    extra_columns: list[list[Column]] = [[] for _ in panels]
    last_bottom = header.y1
    last_kind = "header"  # what the previous body line was
    index = header_index + 1
    while index < len(lines):
        line = lines[index]
        segments = page.free(line)
        if line.y0 - last_bottom > 2.8 * page.line_height:
            break
        if not segments:
            index += 1
            continue
        if _header_columns(line, page) is not None:
            break
        text = " ".join(s.text for s in segments)
        if V.section_for(text) or V.normalize_label(text) in (V.STUDENT_CONTEXT | V.INSTITUTION_CONTEXT):
            break
        if len(segments) == 1 and V.section_for(_clean_label(segments[0].text)):
            break
        if _pair_line(segments) and not any(_data_like([s for s in segments if in_panel(s, p)], panel) for p, panel in enumerate(panels)):
            # A labelled total inside the table ("Credit Attempted: 10.00")
            # belongs to the current group when course rows follow it, or
            # when it closes the rows printed directly above it. Otherwise
            # (a grand total, the document's summary) the table has ended.
            continues = False
            for ahead in lines[index + 1 : index + 4]:
                ahead_segments = page.free(ahead)
                if ahead.y0 - line.y1 > 2.8 * page.line_height:
                    break
                if any(_section_heading(s) for s in ahead_segments):
                    break
                if any(_data_like([s for s in ahead_segments if in_panel(s, p)], panel) for p, panel in enumerate(panels)):
                    continues = True
                    break
            closes_rows = last_kind == "row" and line.y0 - last_bottom < 1.5 * page.line_height
            if not continues and not closes_rows:
                break
            scope = " · ".join(v for v in groups[0].values()) or None
            if scope:
                page.line_scope[line.index] = scope
            last_bottom = line.y1
            last_kind = "total"
            index += 1
            continue

        consumed_any = False
        special = False  # a group, total or section line rather than a course row
        for p, panel in enumerate(panels):
            mine = [s for s in segments if in_panel(s, p)]
            if not mine:
                continue
            values = _is_group_line(mine)
            if values:
                groups[p] = dict(values)
                group_frags[p] = {k: [_seg(s, page.number) for s in mine] for k in values}
                page.use(*mine)
                consumed_any = True
                special = True
                continue
            first = min(mine, key=lambda s: s.x0)
            if V.TOTAL_ROW.search(first.text):
                scope = " · ".join(groups[p].values()) or None
                label_frag = _seg(first, page.number)
                for segment in mine:
                    if segment is first:
                        continue
                    column_index = _column_for(_seg(segment, page.number), panel)
                    caption = panel[column_index].header if column_index is not None else None
                    label = _clean_label(first.text)
                    page_label = f"{label} {caption}".strip() if caption and not re.search(r"gpa", label, re.I) else label
                    rows_frags = [_seg(s, page.number) for s in mine]
                    page_scope = scope
                    layout.summary.append(
                        SummaryItem(
                            label=page_label,
                            label_frags=[label_frag],
                            value_frags=[_seg(segment, page.number)],
                            page=page.number,
                            scope=page_scope,
                            evidence=evidence_of(rows_frags),
                        )
                    )
                # "GPA = 3.90" in one run.
                inline = re.match(r"^(.*?gpa)\s*[=:+]?\s*(\d+(?:\.\d+)?)\s*$", first.text, re.I)
                if inline and len(mine) == 1:
                    words = first.words
                    layout.summary.append(
                        SummaryItem(
                            label=_clean_label(inline.group(1)),
                            label_frags=[Fragment(words[:-1], page.number, first.line_index)] if len(words) > 1 else [],
                            value_frags=[Fragment(words[-1:], page.number, first.line_index)],
                            page=page.number,
                            scope=" · ".join(groups[p].values()) or None,
                            evidence=first.text,
                        )
                    )
                page.use(*mine)
                consumed_any = True
                special = True
                continue
            # A line that names a sub-section of the record (a school, a
            # program) opens a new group of rows.
            if len(mine) <= 3 and _context_line(mine, panel, p == 0):
                ordered = sorted(mine, key=lambda s: s.x0)
                text = "   ".join(s.text for s in ordered)
                # Term / year captions printed beside the section name; the
                # name itself is prose ("… Summer School …" is not a term).
                values = _group_values(" ".join(s.text for s in ordered[1:]))
                year = V.ACADEMIC_YEAR.search(ordered[0].text)
                if year and "academic_year" not in values:
                    values["academic_year"] = year.group(0)
                groups[p] = {**values, "section": text}
                group_frags[p] = {k: [_seg(s, page.number) for s in mine] for k in groups[p]}
                page.use(*mine)
                consumed_any = True
                special = True
                continue
            fragments = [_seg(s, page.number) for s in sorted(mine, key=lambda s: s.x0)]
            assigned: dict[int, list[Fragment]] = {}
            loose: list[Fragment] = []
            for fragment in fragments:
                column_index = _column_for(fragment, panel)
                if column_index is None:
                    loose.append(fragment)
                else:
                    assigned.setdefault(column_index, []).append(fragment)
            previous = rows[p][-1] if rows[p] else None
            if (
                previous is not None
                and len(fragments) == 1
                and line.y0 - max(f.y1 for f in previous.row_frags) < 0.6 * page.line_height
                and not re.fullmatch(r"[\d.,/\s%()-]+", fragments[0].text)
            ):
                # A lone text run tucked under a row continues that row's
                # cell (a wrapped course title), or fills the cell it left
                # empty.
                fragment = fragments[0]
                column_index = next(iter(assigned)) if assigned else None
                if column_index is not None and (
                    column_index not in previous.cells
                    or abs(previous.cells[column_index][0].x0 - fragment.x0) <= 12
                ):
                    previous.cells.setdefault(column_index, []).append(fragment)
                    previous.line_indices.append(line.index)
                    previous.row_frags.append(fragment)
                    page.use(*mine)
                    consumed_any = True
                    continue
                if loose:
                    own_loose = [f for row, f in unheaded[p] if row is previous]
                    if not own_loose or any(abs(f.x0 - fragment.x0) <= 12 for f in own_loose):
                        unheaded[p].append((previous, fragment))
                        previous.line_indices.append(line.index)
                        previous.row_frags.append(fragment)
                        page.use(*mine)
                        consumed_any = True
                        continue
            row = CourseRow(
                cells=assigned,
                group=dict(groups[p]),
                group_frags={k: list(v) for k, v in group_frags[p].items()},
                page=page.number,
                line_indices=[line.index],
                row_frags=fragments,
            )
            rows[p].append(row)
            unheaded[p].extend((row, f) for f in loose)
            page.use(*mine)
            consumed_any = True
        if consumed_any or segments:
            last_bottom = line.y1
            last_kind = "row" if consumed_any and not special else "other"
        index += 1

    tables: list[CourseTable] = []
    for p, panel in enumerate(panels):
        # Values under no printed caption form their own columns, named
        # only when their values show what they are.
        clusters: list[tuple[float, float, list[tuple[CourseRow, Fragment]]]] = []
        for row, fragment in sorted(unheaded[p], key=lambda item: item[1].x0):
            for i, (x0, x1, members) in enumerate(clusters):
                if _overlap(fragment.x0, fragment.x1, x0 - 6, x1 + 6) > 0:
                    members.append((row, fragment))
                    clusters[i] = (min(x0, fragment.x0), max(x1, fragment.x1), members)
                    break
            else:
                clusters.append((fragment.x0, fragment.x1, [(row, fragment)]))
        for x0, x1, members in clusters:
            column = Column(role=None, header=None, display=None, x0=x0, x1=x1, inferred=True)
            panel.append(column)
            column_index = len(panel) - 1
            for row, fragment in members:
                row.cells.setdefault(column_index, []).append(fragment)
            extra_columns[p].append(column)
        has_title = any(c.role == "title" for c in panel)
        for column_index, column in enumerate(panel):
            if column.role:
                continue
            values = [fragments_text(row.cells[column_index]) for row in rows[p] if column_index in row.cells]
            if column.header and sum(ch.isalpha() for ch in column.header) >= 3 and not column.inferred:
                continue  # a printed caption outside the vocabulary: kept as printed
            role, display = _infer_role(values, has_title)
            if role:
                column.role, column.display, column.inferred = role, display, True
                has_title = has_title or role == "title"
            else:
                column.header = None
        # A course row has two or more cells, or is a lone course title
        # (a course listed without results yet).
        kept = [
            row
            for row in rows[p]
            if sum(1 for fs in row.cells.values() if fragments_text(fs)) >= 2
            or any(panel[i].role == "title" and len(fragments_text(fs)) >= 3 for i, fs in row.cells.items())
        ]
        used_columns = {i for row in kept for i in row.cells}
        if kept:
            tables.append(
                CourseTable(
                    columns=[c if i in used_columns else Column(None, None, None, c.x0, c.x1) for i, c in enumerate(panel)],
                    rows=kept,
                    page=page.number,
                    header_line=header_index,
                )
            )
    return tables


# --- sections ------------------------------------------------------------------------


def legible(text: str) -> bool:
    """Text a person could read: mostly letters/digits/spaces, and no long
    consonant runs (OCR of table shading reads as "SSC~C“‘“~*S*S*S")."""

    text = text.strip()
    if sum(ch.isalnum() for ch in text) < 2:
        return False
    plain = sum(ch.isalnum() or ch.isspace() or ch in ".,:;/()-&'%#+=@" for ch in text)
    if plain < 0.85 * len(text):
        return False
    return not re.search(r"[b-df-hj-np-tv-xzB-DF-HJ-NP-TV-XZ]{6,}", text)


def _section_heading(segment: Segment) -> V.Section | None:
    text = _clean_label(segment.text)
    if len(text.split()) > 6:
        return None
    return V.section_for(text)


def _parse_sections(page: _Page, layout: TranscriptLayout) -> None:
    lines = page.lines
    for index, line in enumerate(lines):
        free = page.free(line)
        headings = [(s, _section_heading(s)) for s in free]
        headings = [(s, sec) for s, sec in headings if sec]
        # A heading stands on its own: any other run on the line is another
        # heading or far away (a separate panel). "Honors: Algebra II" is a
        # course, not the Honors section.
        headings = [
            (s, sec)
            for s, sec in headings
            if not s.text.rstrip().endswith(":") or len(s.words) > 1
            if all(
                _section_heading(o) or o.x0 - s.x1 > 150 or s.x0 - o.x1 > 150
                for o in free
                if o is not s
            )
        ]
        if not headings:
            continue
        for position, (segment, section) in enumerate(headings):
            width = segment.x1 - segment.x0
            x0 = segment.x0 - max(60.0, width)
            if position > 0:
                x0 = max(x0, headings[position - 1][0].x1 + 5)
            x1 = headings[position + 1][0].x0 - 5 if position + 1 < len(headings) else 1e9
            page.use(segment)
            page.barriers.append(line.y0)
            heading = _clean_label(segment.text)
            content: list[list[Segment]] = []
            last_bottom = line.y1
            for follower in lines[index + 1 : index + 16]:
                mine = [s for s in page.free(follower) if x0 <= (s.x0 + s.x1) / 2 < x1]
                if follower.y0 - last_bottom > 2.5 * page.line_height:
                    break
                if not mine:
                    continue
                if any(_section_heading(s) for s in mine) or _header_columns(follower, page) is not None:
                    break
                text = " ".join(s.text for s in mine)
                if V.normalize_label(text) in (V.STUDENT_CONTEXT | V.INSTITUTION_CONTEXT | V.PROGRAM_CONTEXT):
                    break
                if section.category != V.CERTIFICATION and V.CERTIFICATION_WORDS.search(text):
                    break
                if not legible(text):
                    last_bottom = follower.y1
                    continue
                content.append(sorted(mine, key=lambda s: s.x0))
                last_bottom = follower.y1
            _section_entries(page, layout, section, heading, content)


def _section_entries(
    page: _Page, layout: TranscriptLayout, section: V.Section, heading: str, content: list[list[Segment]]
) -> None:
    if not content:
        return
    # A caption row ("Subject Area | Credit Req'd | Completed") above rows
    # of values names the values.
    captions: list[Segment] | None = None
    first = content[0]
    if (
        len(first) >= 2
        and all(not re.search(r"\d", s.text) for s in first)
        and len(content) > 1
        and any(re.search(r"\d", s.text) for row in content[1:] for s in row)
    ):
        captions = first
        page.use(*first)
        content = content[1:]
    whole_line = section.category in (V.GRADING, V.NOTES, V.HONORS, V.ACTIVITIES, V.CERTIFICATION, V.ACCREDITATION)
    for row in content:
        page.use(*row)
        fragments = [_seg(s, page.number) for s in row]
        if section.category == V.SUMMARY and captions:
            scope = _clean_label(row[0].text)
            for segment in row[1:]:
                caption = max(captions, key=lambda c: _overlap(segment.x0, segment.x1, c.x0 - 6, c.x1 + 6))
                if _overlap(segment.x0, segment.x1, caption.x0 - 6, caption.x1 + 6) <= 0:
                    continue
                layout.summary.append(
                    SummaryItem(
                        label=_clean_label(caption.text),
                        label_frags=[_seg(caption, page.number)],
                        value_frags=[_seg(segment, page.number)],
                        page=page.number,
                        scope=scope,
                        evidence=evidence_of([_seg(caption, page.number), *fragments]),
                    )
                )
            continue
        colon = re.match(r"^([^:]{2,60}):\s*(\S.*)$", " ".join(s.text for s in row))
        if whole_line or len(row) == 1 and not colon:
            layout.entries.append(
                SectionEntry(section.category, section.entry_label, None, [], fragments, page.number, heading)
            )
            continue
        if colon and len(row) == 1 and len(colon.group(1).split()) <= 6:
            words = row[0].words
            split = next((i for i, w in enumerate(words) if w.text.endswith(":")), None)
            if split is not None and split + 1 < len(words):
                layout.entries.append(
                    SectionEntry(
                        section.category,
                        section.entry_label,
                        _clean_label(" ".join(w.text for w in words[: split + 1])),
                        [Fragment(words[: split + 1], page.number, row[0].line_index)],
                        [Fragment(words[split + 1 :], page.number, row[0].line_index)],
                        page.number,
                        heading,
                    )
                )
                continue
        label_segment, rest = row[0], row[1:]
        if captions and rest:
            parts = []
            for segment in rest:
                caption = max(captions, key=lambda c: _overlap(segment.x0, segment.x1, c.x0 - 6, c.x1 + 6))
                named = _overlap(segment.x0, segment.x1, caption.x0 - 6, caption.x1 + 6) > 0
                parts.append(f"{_clean_label(caption.text)}: {segment.text}" if named else segment.text)
            layout.entries.append(
                SectionEntry(
                    section.category,
                    section.entry_label,
                    _clean_label(label_segment.text),
                    [_seg(label_segment, page.number)],
                    [_seg(s, page.number) for s in rest],
                    page.number,
                    heading,
                    display_value=" · ".join(parts),
                )
            )
            continue
        layout.entries.append(
            SectionEntry(
                section.category,
                section.entry_label,
                _clean_label(label_segment.text) if rest else None,
                [_seg(label_segment, page.number)] if rest else [],
                [_seg(s, page.number) for s in rest] if rest else fragments,
                page.number,
                heading,
            )
        )


# --- label / value pairs --------------------------------------------------------------


_URL_LABEL = re.compile(r"^(?:https?|www|ftp|mailto)$", re.I)


def _valid_label(text: str) -> bool:
    text = _clean_label(text)
    words = text.split()
    if not words or len(words) > 6 or len(text) > 60:
        return False
    if _URL_LABEL.match(text) or re.search(r"\d", text.replace("#", "")):
        return False
    letters = sum(ch.isalpha() for ch in text)
    return letters >= 2 and letters >= 0.6 * len(text.replace(" ", ""))


def _is_known_label(text: str) -> bool:
    return V.field_spec(_clean_label(text)) is not None


def _colon_pairs(segment: Segment, page: int) -> list[tuple[list[Word], list[Word], list[Word]]] | None:
    """(label words, separator words, value words) for each "Label: value"
    inside one run. None when the run holds no valid labelled pair."""

    words = segment.words
    marks = [
        i for i, w in enumerate(words)
        if (w.text.endswith((":", "=")) and len(w.text) > 1) or w.text in (":", "=")
    ]
    if not marks:
        return None
    pairs: list[tuple[list[Word], list[Word], list[Word]]] = []
    start = 0
    for k, mark in enumerate(marks):
        if mark < start:
            continue
        label_words = words[start:mark] if words[mark].text in (":", "=") else words[start : mark + 1]
        separator = [words[mark]] if words[mark].text in (":", "=") else []
        if not label_words or not _valid_label(" ".join(w.text for w in label_words)):
            return pairs or None
        end = len(words)
        if k + 1 < len(marks):
            # The next label starts after at least one value word: walk back
            # over its capitalised words.
            nxt = marks[k + 1]
            begin = nxt if words[nxt].text in (":", "=") else nxt
            j = begin
            while j - 1 > mark + 1 and nxt - (j - 1) < 4 and re.fullmatch(r"[A-Z][A-Za-z.'/&-]*", words[j - 1].text):
                j -= 1
            if words[nxt].text in (":", "="):
                j = min(j, nxt - 1) if nxt - 1 > mark + 1 else j
            end = j
        pairs.append((label_words, separator, words[mark + 1 : end]))
        start = end
    return pairs or None


def _below(page: _Page, line: Line, x0: float, x1: float, limit: int = 3) -> list[Segment]:
    """Runs directly below a caption that has no value beside it."""

    found: list[Segment] = []
    bottom = line.y1
    for follower in page.lines[line.index + 1 : line.index + 1 + limit]:
        if follower.y0 - bottom > 1.3 * page.line_height:
            break
        candidates = [
            s for s in page.free(follower)
            if _overlap(s.x0, s.x1, x0 - 6, max(x1, x0 + 120)) > 0 and s.x0 >= x0 - 12
        ]
        if not candidates:
            break
        if any(_colon_pairs(s, page.number) or _is_known_label(s.text) for s in candidates):
            break
        found.extend(sorted(candidates, key=lambda s: s.x0)[:2])
        bottom = follower.y1
    return found


def _continuation(page: _Page, line: Line, value: Fragment) -> list[Segment]:
    """A value wrapped onto the next line(s), left-aligned with its start."""

    found: list[Segment] = []
    bottom = line.y1
    for follower in page.lines[line.index + 1 : line.index + 3]:
        if follower.y0 - bottom > 0.8 * page.line_height:
            break
        candidates = [s for s in page.free(follower) if abs(s.x0 - value.x0) <= 8]
        if len(candidates) != 1:
            break
        candidate = candidates[0]
        if _colon_pairs(candidate, page.number) or _is_known_label(candidate.text) or _section_heading(candidate):
            break
        # Only when nothing else on that line sits left of the value in
        # the value's column (that would be the next labelled row).
        others = [s for s in page.free(follower) if s is not candidate and s.x1 > value.x0 - 150 and s.x0 < value.x0]
        if others:
            break
        found.append(candidate)
        bottom = follower.y1
    return found


_RESULT_SHAPE = re.compile(r"^(?:\d{1,3}(?:\.\d{1,2})?|[A-F][+-]?|\d{1,3}\s*\([A-F][+-]?\))$")


def _parse_pairs(page: _Page, layout: TranscriptLayout) -> None:
    for line in page.lines:
        segments = sorted(page.free(line), key=lambda s: s.x0)
        # A row of captions ("Grade   Birthdate   Counselor") labels the
        # values printed beneath it, not the runs beside each caption.
        captions = [s for s in segments if _is_known_label(s.text) and ":" not in s.text]
        others = [s for s in segments if s not in captions and s.text.strip() not in (":", "=")]
        caption_row = len(captions) >= 2 and len(others) <= 1
        # Grade/credit-shaped runs mean this line is a row of an unrecognised
        # course table: "English I: Literature & Writing   1.0   A" is a
        # course, not a field.
        course_like = sum(1 for s in segments if _RESULT_SHAPE.match(s.text.strip())) >= 2
        # A two-run line whose first run is a caption is a label/value row
        # even for everyday caption words ("Faculty   School of Business").
        two_runs = len(segments) == 2
        i = 0
        while i < len(segments):
            segment = segments[i]
            if id(segment) in page.used:
                i += 1
                continue
            class_of = _CLASS_OF.match(segment.text.strip())
            if class_of:
                words = segment.words
                page.use(segment)
                _add_pair(
                    page, layout,
                    Pair([Fragment(words[:-1], page.number, line.index)], [Fragment(words[-1:], page.number, line.index)],
                         page.number, "known_label"),
                )
                i += 1
                continue
            inline = _colon_pairs(segment, page.number)
            if inline and course_like and not any(
                _is_known_label(text := " ".join(w.text for w in label)) and not V.is_weak_label(_clean_label(text))
                for label, _, _ in inline
            ):
                i += 1
                continue
            if inline:
                for label_words, separator, value_words in inline:
                    label_frag = Fragment(label_words, page.number, line.index)
                    extra = [Fragment(separator, page.number, line.index)] if separator else []
                    value_frags: list[Fragment] = []
                    if value_words:
                        value_frags = [Fragment(value_words, page.number, line.index)]
                    elif inline[-1][0] is label_words and i + 1 < len(segments) and not _is_label_run(segments[i + 1]):
                        value_frags = [_seg(segments[i + 1], page.number)]
                        page.use(segments[i + 1])
                        i += 1
                    else:
                        below = _below(page, line, label_frag.x0, label_frag.x1)
                        value_frags = [_seg(s, page.number) for s in below]
                        page.use(*below)
                    if value_frags and len(value_frags) == 1 and value_frags[0].line_index == line.index:
                        more = _continuation(page, line, value_frags[0])
                        value_frags += [_seg(s, page.number) for s in more]
                        page.use(*more)
                    _add_pair(page, layout, Pair([label_frag], value_frags, page.number, "separator", extra))
                page.use(segment)
                i += 1
                continue
            # "Label || : || value" or "Label: || value"
            if i + 2 < len(segments) and segments[i + 1].text.strip() in (":", "=") and _valid_label(segment.text):
                value = segments[i + 2]
                label_frag, value_frag = _seg(segment, page.number), _seg(value, page.number)
                more = _continuation(page, line, value_frag)
                page.use(segment, segments[i + 1], value, *more)
                _add_pair(
                    page,
                    layout,
                    Pair([label_frag], [value_frag] + [_seg(s, page.number) for s in more], page.number, "separator",
                         [_seg(segments[i + 1], page.number)]),
                )
                i += 3
                continue
            weak = V.is_weak_label(_clean_label(segment.text))
            if (
                _is_known_label(segment.text)
                and not caption_row
                and (not weak or (two_runs and i == 0))
                and i + 1 < len(segments)
                and not _is_label_run(segments[i + 1])
            ):
                value = segments[i + 1]
                if value.x0 - segment.x1 < 0.45 * page.width:
                    label_frag, value_frag = _seg(segment, page.number), _seg(value, page.number)
                    more = _continuation(page, line, value_frag)
                    page.use(segment, value, *more)
                    _add_pair(
                        page, layout,
                        Pair([label_frag], [value_frag] + [_seg(s, page.number) for s in more], page.number, "known_label"),
                    )
                    i += 2
                    continue
            if _is_known_label(segment.text) and not re.search(r"\d", segment.text) and (caption_row or not weak):
                below = _below(page, line, segment.x0, segment.x1, limit=1)
                if below:
                    page.use(segment, below[0])
                    _add_pair(
                        page, layout,
                        Pair([_seg(segment, page.number)], [_seg(below[0], page.number)], page.number, "label_above"),
                    )
            i += 1


def _is_label_run(segment: Segment) -> bool:
    text = segment.text.strip()
    return text in (":", "=") or bool(_colon_pairs(segment, 0)) or _is_known_label(text) or text.endswith(":")


_CLASS_OF = re.compile(r"^class\s+of\s+((?:19|20)\d{2})$", re.I)


def _add_pair(page: _Page, layout: TranscriptLayout, pair: Pair) -> None:
    if not pair.value or not legible(pair.value):
        return
    if V.normalize_label(pair.label) in V.IGNORED_LABELS:
        return
    line_index = pair.label_frags[0].line_index if pair.label_frags else pair.value_frags[0].line_index
    pair.scope = page.line_scope.get(line_index)
    y = pair.label_frags[0].y0 if pair.label_frags else pair.value_frags[0].y0
    x = pair.label_frags[0].x0 if pair.label_frags else pair.value_frags[0].x0
    pair.context = _context_at(page, y, x)
    pair.in_letterhead = page.letterhead_bottom is not None and y < page.letterhead_bottom
    layout.pairs.append(pair)


def _context_at(page: _Page, y: float, x: float) -> str | None:
    """The context heading governing a position: the nearest one above in
    the same column, unless a table/section heading intervenes."""

    def center(context: tuple[float, float, float, str]) -> float:
        return (context[1] + context[2]) / 2

    best = None
    for context in page.contexts:
        hy, _, _, kind = context
        if hy >= y or any(hy < barrier < y for barrier in page.barriers):
            continue
        # Headings on one line split the page at the midpoints between them.
        peers = sorted((c for c in page.contexts if abs(c[0] - hy) < 2), key=center)
        index = peers.index(context)
        left = (center(peers[index - 1]) + center(context)) / 2 if index > 0 else -1e9
        right = (center(context) + center(peers[index + 1])) / 2 if index + 1 < len(peers) else 1e9
        if left <= x < right and (best is None or hy > best[0]):
            best = (hy, kind)
    return best[1] if best else None


def _context_kind(text: str) -> str | None:
    key = V.normalize_label(_clean_label(text))
    if key in V.STUDENT_CONTEXT:
        return "student"
    if key in V.INSTITUTION_CONTEXT:
        return "institution"
    if key in V.PROGRAM_CONTEXT:
        return "program"
    return None


def _find_contexts(page: _Page) -> None:
    """Heading-only lines ("Student Information   School Information")
    that set the context of the fields beneath them."""

    for line in page.lines:
        segments = page.free(line)
        kinds = [_context_kind(s.text) for s in segments]
        if segments and all(kinds):
            for segment, kind in zip(segments, kinds):
                page.contexts.append((line.y0, segment.x0, segment.x1, kind))
            page.use(*segments)


# --- letterhead, titles, certification --------------------------------------------------


_PHONE = re.compile(r"^(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]\d{3,4}$")
_DATE_LINE = re.compile(
    r"^(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})$",
    re.I,
)
_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
_URL = re.compile(r"^(?:https?://|www\.)\S+$", re.I)
_ADDRESS = re.compile(r"\d.*[A-Za-z]{2}|[A-Za-z]{2}.*\d{4,}|,|^#\s?\d+[A-Za-z]?$")
_CONTACT_SPECS = {"transcript.student.phone", "transcript.student.email", "transcript.student.address",
                  "transcript.institution.website", "transcript.institution.contact"}


def _labelled(segment: Segment) -> bool:
    """A run that labels a student/record field (contact labels excluded:
    those also appear in an institution's letterhead)."""

    inline = _colon_pairs(segment, 0)
    labels = [" ".join(w.text for w in label) for label, _, _ in inline] if inline else [segment.text]
    for label in labels:
        spec = V.field_spec(_clean_label(label))
        if (spec and spec.field_id not in _CONTACT_SPECS) or (inline and not spec):
            return True
    return False


def _letterhead(page: _Page, layout: TranscriptLayout) -> None:
    """The institution's name and the unlabeled address/contact lines
    directly beneath it, at the top of the first page — above the first
    student/record field, context heading or table."""

    stop = min([y for y, *_ in page.contexts] + page.barriers + [1e9])
    for line in page.lines:
        if line.y0 >= stop:
            break
        if any(_labelled(s) for s in page.free(line)):
            stop = line.y0
            break
    page.letterhead_bottom = stop
    institution: Segment | None = None
    for line in page.lines:
        if line.y0 >= stop:
            break
        for segment in page.free(line):
            text = segment.text.strip()
            if V.TITLE_WORDS.search(text) or ":" in text or re.search(r"\d", text):
                continue
            words = [w for w in re.findall(r"[A-Za-z&.'-]+", text) if sum(ch.isalpha() for ch in w) >= 2]
            others = [w for w in words if not V.INSTITUTION_WORDS.fullmatch(w)]
            if not (V.INSTITUTION_WORDS.search(text) and len(words) >= 2 and others):
                continue
            # A district's name may be followed directly by its school's.
            if institution is None or (
                re.search(r"\bdistrict\b", institution.text, re.I)
                and abs(segment.x0 - institution.x0) < 30
                and segment.bbox[1] - institution.bbox[3] < 1.5 * page.line_height
            ):
                district = re.search(r"\bdistrict\b", text, re.I) is not None
                layout.pairs.append(
                    Pair([], [_seg(segment, page.number)], page.number, "letterhead", in_letterhead=True,
                         shape_label="District" if district else "Institution")
                )
                page.use(segment)
                institution = segment
    if institution is None:
        return
    # Address and contact lines run on directly beneath the name, in its
    # column; the block ends at the first wide gap.
    address: list[Fragment] = []
    left, right = institution.x0 - 10, institution.x1 + 10
    bottom = institution.bbox[3]
    for line in page.lines:
        if line.y0 <= institution.bbox[1] or line.y0 >= stop:
            continue
        if line.y0 - bottom > 3 * page.line_height:
            break
        # The block is the name's own column (overlapping its span): a
        # centred letterhead's lines, or a left-aligned one's.
        in_column = [s for s in page.free(line) if _overlap(s.x0, s.x1, left, right) > 0]
        if not in_column:
            continue
        if any(_DATE_LINE.match(s.text.strip()) for s in in_column):
            break  # a dated line starts the document body
        bottom = line.y1
        for segment in in_column:
            text = segment.text.strip()
            shape = (
                "Institution Email" if _EMAIL.match(text)
                else "Website" if _URL.match(text)
                else "Institution Phone"
                if _PHONE.match(text) and sum(ch.isdigit() for ch in text) >= 7 and not V.ACADEMIC_YEAR.search(text)
                else None
            )
            if shape:
                layout.pairs.append(
                    Pair([], [_seg(segment, page.number)], page.number, "letterhead", in_letterhead=True, shape_label=shape)
                )
                page.use(segment)
            elif _ADDRESS.search(text) and not V.TITLE_WORDS.search(text) and ":" not in text and len(text.split()) <= 9:
                address.append(_seg(segment, page.number))
                page.use(segment)
    if address:
        layout.pairs.append(
            Pair([], address, page.number, "letterhead", in_letterhead=True, shape_label="Institution Address")
        )


def _titles(page: _Page, layout: TranscriptLayout) -> None:
    for line in page.lines[:12]:
        for segment in page.free(line):
            if V.TITLE_WORDS.search(segment.text) and len(segment.text.split()) <= 8:
                layout.titles.append(segment.text.strip())
                page.use(segment)


def _certification(page: _Page, layout: TranscriptLayout) -> None:
    lines = page.lines
    index = 0
    while index < len(lines):
        line = lines[index]
        for segment in page.free(line):
            text = segment.text.strip()
            if V.CERTIFICATION_WORDS.search(text) and len(text.split()) >= 3:
                fragments = [_seg(segment, page.number)]
                page.use(segment)
                bottom, x0 = line.y1, segment.x0
                for follower in lines[index + 1 : index + 5]:
                    if follower.y0 - bottom > 0.9 * page.line_height or fragments_text(fragments).rstrip().endswith("."):
                        break
                    nxt = [s for s in page.free(follower) if _overlap(s.x0, s.x1, x0 - 40, segment.x1 + 40) > 0]
                    if len(nxt) != 1:
                        break
                    fragments.append(_seg(nxt[0], page.number))
                    page.use(nxt[0])
                    bottom = follower.y1
                layout.entries.append(
                    SectionEntry(V.CERTIFICATION, "Certification Statement", None, [], fragments, page.number, "")
                )
            elif (
                V.SIGNATORY_WORDS.search(text)
                and len(text.split()) <= 6
                and ":" not in text
                and not re.search(r"\d", text)
            ):
                page.use(segment)
                layout.entries.append(
                    SectionEntry(V.CERTIFICATION, "Signatory", None, [], [_seg(segment, page.number)], page.number, "")
                )
        index += 1


# --- entry point ------------------------------------------------------------------------------


def reconstruct(pages: list[tuple[int, list[Word]]]) -> TranscriptLayout:
    """Logical transcript units for a document's pages (page number, words
    in page space)."""

    layout = TranscriptLayout()
    first_page = next((number for number, words in pages if words), None)
    for number, words in pages:
        if not words:
            continue
        page = _page(number, words)
        _titles(page, layout)
        for index, line in enumerate(page.lines):
            columns = _header_columns(line, page)
            if columns is not None:
                layout.tables.extend(_parse_table(page, index, columns, layout))
        _find_contexts(page)
        _parse_sections(page, layout)
        if number == first_page:
            _letterhead(page, layout)
        _parse_pairs(page, layout)
        _certification(page, layout)
    return layout
