"""Federal Register FAR final rule (PDF) → rule facts, preamble sections,
threshold tables and amendatory instructions.

A Federal Register issue prints a FAR rule in three columns, with tables
spanning the page width. Pages are read band by band: the columns above a
spanning table (left to right, top to bottom), the table, then the columns
below it — the order a reader follows, so "■4. Amend section 25.402 …
revising table 1" is directly followed by that table.

One PDF often carries several FR documents (the FAC introduction, the rule,
the Small Entity Compliance Guide); each ends with "[FR Doc. …]". The rule
is the document whose ACTION is "Final rule".

Tables are the GPO dot-leader layout: a label column ending in a dot
leader ("WTO GPA ........") and right-aligned value columns, under headings
that wrap over several lines ("Supply contract / (equal to or /
exceeding)"). Group rows ("FTAs:") and labels wrapped onto a second line
("… Guate-" / "mala, …") are kept; a dot-leader cell is an empty value.

Text is never rewritten: whitespace is normalized and a line-end hyphen
before a lowercase word is joined as printed ("Guate-mala"). Deterministic —
native PDF text only, no OCR, no AI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.source_structure.pdf_structure import Line, Segment, build_lines, native_words

BBox = tuple[float, float, float, float]

_SQUARE = "■■▪"
_LEADER = re.compile(r"\s*(?:\.\s?){4,}\s*$")
_ONLY_LEADER = re.compile(r"^(?:\.\s?){3,}$")
_VALUE = re.compile(r"^\$?\d[\d,]*(?:\.\d+)?$")
_FR_HEADER = re.compile(
    r"Federal Register\s*/\s*Vol\.\s*(?P<vol>\d+),\s*No\.\s*(?P<no>\d+)\s*/\s*(?P<date>[^/]+?)\s*/\s*Rules and Regulations",
    re.I,
)
_FR_PAGE = re.compile(r"(?:^|\s)(\d{4,6})(?:\s|$)")
_FR_DOC = re.compile(r"\[FR Doc\.\s*(?P<doc>\d{4}[–-]\d+)", re.I)
_CAPTION = re.compile(
    r"^(?P<caption>AGENCY|ACTION|SUMMARY|DATES|ADDRESSES|FOR FURTHER INFORMATION CONTACT|SUPPLEMENTARY INFORMATION):\s*(?P<text>.*)$",
    re.S,
)
_ROMAN_SECTION = re.compile(r"^(?P<num>[IVXL]+)\.\s+(?P<title>\S.{0,220})$", re.S)
_PART_HEADING = re.compile(r"^PART\s+(?P<part>\d{1,2})\s*[—–-]\s*(?P<title>.+)$")
_AMENDED_HEADING = re.compile(r"^(?P<section>\d{1,2}\.\d{3,4}(?:[–-]\d+)?)\s+\[Amended\]$")
_SECTION_TITLE = re.compile(r"^(?P<section>\d{1,2}\.\d{3,4}(?:[–-]\d+)?)\s+(?P<title>[A-Z][^*]*?)\.?\s*(?:\*\s*)*(?:\(\w\)\s*(?:\*\s*)*)?$")
_INSTRUCTION = re.compile(r"^[" + _SQUARE + r"]\s*(?P<num>\d+)\.\s*(?P<text>.*)$", re.S)
_SUB_ITEM = re.compile(r"[" + _SQUARE + r"]\s*(?P<letter>[a-z])\.\s*")
_SECTION_REF = re.compile(r"\bsection\s+(?P<section>\d{1,2}\.\d{3,4}(?:[–-]\d+)?)", re.I)
_PARAGRAPHS = re.compile(
    r"(?:the introductory text of\s+)?paragraphs?\s+(?P<paras>\((?:[^)]+)\)(?:\([^)]+\))*(?:,?\s*(?:and\s+)?\((?:[^)]+)\)(?:\([^)]+\))*)*)",
    re.I,
)
_QUOTED = re.compile(r"[‘“'`]{1,2}(?P<value>[^‘’“”']+?)[’”']{1,2}")
_REVISED_DATE = re.compile(r"\((?P<date>(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?\s+\d{4})\)\s*$")
_FAR_NUMBER = re.compile(r"\d{1,2}\.\d{3,4}(?:[–-]\d+)?")


def far_number(text: str) -> str:
    """"52.204–8" (Federal Register en dash) → "52.204-8"."""

    return text.replace("–", "-").replace("—", "-")


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def join_lines(lines: list[str]) -> str:
    out = ""
    for line in (clean(l) for l in lines):
        if not line:
            continue
        if not out:
            out = line
        elif out.endswith("-") and not out.endswith(" -") and line[:1].islower():
            out += line
        else:
            out += " " + line
    return out


@dataclass
class Block:
    page: int  # 1-based PDF page
    fr_page: str | None  # printed Federal Register page ("12489")
    text: str
    bbox: BBox
    table: "LeaderTable | None" = None


@dataclass
class TableRow:
    label: str
    group: str | None
    values: list[str | None]
    text: str  # the printed line(s), for evidence
    bbox: BBox


@dataclass
class LeaderTable:
    page: int
    fr_page: str | None
    caption: str | None
    headers: list[str]  # label column header, then one per value column
    rows: list[TableRow]
    bbox: BBox
    header_text: str


@dataclass
class FrDocument:
    blocks: list[Block]
    fr_doc: str | None = None

    def caption(self, name: str) -> str | None:
        for block in self.blocks:
            match = _CAPTION.match(block.text)
            if match and match.group("caption").upper() == name:
                return clean(match.group("text"))
        return None


# --- reading order ------------------------------------------------------------------------


def _union(boxes: list[BBox]) -> BBox:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _header_info(page) -> tuple[str | None, dict | None]:
    for block in page.get_text("blocks"):
        if block[6] != 0 or block[1] > 50:
            continue
        text = clean(block[4])
        match = _FR_HEADER.search(text)
        if match:
            rest = _FR_HEADER.sub(" ", text)
            number = _FR_PAGE.search(rest)
            return (number.group(1) if number else None), match.groupdict()
    return None, None


def _columns(blocks: list[tuple], width: float) -> list[float]:
    """Left edges of the page's text columns, from its narrow blocks."""

    lefts = sorted(b[0] for b in blocks if (b[2] - b[0]) < 0.45 * width)
    columns: list[float] = []
    for x in lefts:
        if not columns or x - columns[-1] > 60:
            columns.append(x)
    return columns or [0.0]


def _column_of(x0: float, columns: list[float]) -> int:
    index = 0
    for i, left in enumerate(columns):
        if x0 >= left - 12:
            index = i
    return index


def page_blocks(page, page_number: int) -> tuple[list[Block], list[LeaderTable]]:
    """The page's paragraphs in reading order (spanning tables as one block
    each), without the running header, footer and margin stamps."""

    fr_page, _ = _header_info(page)
    width, height = page.rect.width, page.rect.height
    tables = leader_tables(page, page_number, fr_page)
    raw = []
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        x0, y0, x1, y1 = b[:4]
        if y1 < 50 or y0 > height - 45 or x1 < 40:  # running header, footer, rotated margin stamp
            continue
        if any(x0 >= t.bbox[0] - 3 and x1 <= t.bbox[2] + 3 and y0 >= t.bbox[1] - 3 and y1 <= t.bbox[3] + 3 for t in tables):
            continue
        lines = b[4].split("\n")
        text = join_lines(lines)
        if text:
            raw.append((x0, y0, x1, y1, text))
    columns = _columns(raw, width)
    # Bands: the page between spanning tables.
    cuts = sorted(tables, key=lambda t: t.bbox[1])
    bands: list[tuple[float, float, LeaderTable | None]] = []
    top = 0.0
    for table in cuts:
        bands.append((top, table.bbox[1], None))
        bands.append((table.bbox[1], table.bbox[3], table))
        top = table.bbox[3]
    bands.append((top, height + 1, None))
    ordered: list[Block] = []
    for y_top, y_bottom, table in bands:
        if table is not None:
            ordered.append(Block(page_number, fr_page, table.caption or "[table]", table.bbox, table))
            continue
        inside = [r for r in raw if y_top - 1 <= (r[1] + r[3]) / 2 < y_bottom]
        for r in sorted(inside, key=lambda r: (_column_of(r[0], columns), r[1])):
            ordered.append(Block(page_number, fr_page, r[4], r[:4]))
    return ordered, tables


# --- dot-leader tables --------------------------------------------------------------------


def _is_value(text: str) -> bool:
    return bool(_VALUE.match(text.strip()))


def _data_row(line: Line) -> tuple[Segment, list[Segment]] | None:
    segs = sorted(line.segments, key=lambda s: s.x0)
    if len(segs) < 2 or not _LEADER.search(segs[0].text):
        return None
    rest = segs[1:]
    if not all(_is_value(s.text) or _ONLY_LEADER.match(s.text.strip()) for s in rest):
        return None
    if not any(_is_value(s.text) for s in rest):
        return None
    return segs[0], rest


def leader_tables(page, page_number: int, fr_page: str | None = None) -> list[LeaderTable]:
    lines = build_lines(native_words(page))
    tables: list[LeaderTable] = []
    i = 0
    while i < len(lines):
        if _data_row(lines[i]) is None:
            i += 1
            continue
        start = i
        members: list[int] = []
        j = i
        height = max(6.0, lines[i].height)
        while j < len(lines):
            line = lines[j]
            if members and line.y0 - lines[members[-1]].y1 > 2.5 * height:
                break
            if _data_row(line) is not None:
                members.append(j)
                j += 1
                continue
            segs = line.segments
            # A group heading ("FTAs:") or a wrapped label: one segment in
            # the label column, followed by more of the table.
            if len(segs) == 1 and not _is_value(segs[0].text):
                rows_so_far = [_data_row(lines[m]) for m in members]
                label_right = max((r[0].x1 for r in rows_so_far if r is not None), default=segs[0].x1)
                if segs[0].x1 <= label_right + 2 and j + 1 < len(lines) and (
                    _data_row(lines[j + 1]) is not None or len(lines[j + 1].segments) == 1
                ):
                    members.append(j)
                    j += 1
                    continue
            break
        data = [m for m in members if _data_row(lines[m]) is not None]
        if len(data) < 3:
            i = j if j > i else i + 1
            continue
        table = _build_table(lines, start, members, page_number, fr_page)
        if table is not None:
            tables.append(table)
        i = j
    return tables


def _value_columns(rows: list[list[Segment]]) -> list[tuple[float, float]]:
    """Right-aligned value columns: clusters of numeric segments' right edges."""

    rights = sorted(s.x1 for row in rows for s in row if _is_value(s.text))
    clusters: list[list[float]] = []
    for x in rights:
        if clusters and x - clusters[-1][-1] <= 8:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    columns = []
    for cluster in clusters:
        members = [s for row in rows for s in row if _is_value(s.text) and min(cluster) - 1 <= s.x1 <= max(cluster) + 1]
        columns.append((min(s.x0 for s in members), max(cluster)))
    return columns


def _build_table(lines: list[Line], start: int, members: list[int], page_number: int, fr_page: str | None) -> LeaderTable | None:
    data_rows = [(_data_row(lines[m]), m) for m in members]
    value_rows = [d[0][1] for d in data_rows if d[0] is not None]
    columns = _value_columns(value_rows)
    if not columns:
        return None
    label_right = max(d[0][0].x1 for d in data_rows if d[0] is not None)
    label_left = min(lines[m].segments[0].x0 for m in members)

    def column_index(seg: Segment) -> int | None:
        # A value cell: its right edge on a column's; a leader cell: the
        # column its right end reaches.
        best = min(range(len(columns)), key=lambda c: abs(columns[c][1] - seg.x1))
        return best if abs(columns[best][1] - seg.x1) <= 12 else None

    # Header lines directly above the first row: every segment sits over
    # the label column or over exactly one value column.
    zones = [label_right] + [(columns[c][1] + columns[c + 1][0]) / 2 for c in range(len(columns) - 1)] + [10_000.0]

    def header_slot(seg: Segment) -> int | None:
        centre = (seg.x0 + seg.x1) / 2
        if seg.x1 <= columns[0][0] - 4 and seg.x0 >= label_left - 4:
            return 0
        for c in range(len(columns)):
            if zones[c] <= centre < zones[c + 1] and seg.x0 >= zones[c] - 30:
                return c + 1
        return None

    header_lines: list[Line] = []
    k = start - 1
    while k >= 0 and len(header_lines) < 5:
        line = lines[k]
        below = header_lines[0] if header_lines else lines[start]
        if below.y0 - line.y1 > 2.6 * max(6.0, line.height):
            break
        slots = [header_slot(s) for s in line.segments]
        if None in slots or not any(s and s > 0 for s in slots):
            break
        header_lines.insert(0, line)
        k -= 1
    if not header_lines:
        return None
    headers = [[] for _ in range(len(columns) + 1)]
    for line in header_lines:
        for seg in sorted(line.segments, key=lambda s: s.x0):
            headers[header_slot(seg)].append(seg.text)
    header_texts = [join_lines(parts) for parts in headers]

    caption = None
    if k >= 0:
        line = lines[k]
        text = clean(" ".join(s.text for s in line.segments))
        if re.match(r"^TABLE\b", text) and header_lines[0].y0 - line.y1 < 3 * max(6.0, line.height):
            caption = text

    rows: list[TableRow] = []
    group: str | None = None
    group_x0: float | None = None
    dash_members = False
    pending: list[Segment] = []
    for m in members:
        line = lines[m]
        parsed = _data_row(line)
        if parsed is None:
            seg = line.segments[0]
            text = clean(seg.text)
            if text.endswith(":"):
                group, group_x0, dash_members, pending = text[:-1].strip(), seg.x0, False, []
            else:
                pending.append(seg)
            continue
        label_seg, cells = parsed
        label = join_lines([s.text for s in pending] + [_LEADER.sub("", label_seg.text)])
        boxes = [s.bbox for s in pending] + [label_seg.bbox] + [c.bbox for c in cells]
        pending_text = " ".join(clean(s.text) for s in pending)
        pending = []
        member_of = None
        if group is not None:
            starts_dash = label[:1] in "—–-"
            first = not any(r.group == group for r in rows)
            indented = group_x0 is not None and label_seg.x0 > group_x0 + 4
            if first:
                dash_members = starts_dash
                member_of = group if (indented or starts_dash) else None
            elif dash_members:
                member_of = group if starts_dash else None
            else:
                member_of = group if indented else None
            if member_of is None:
                group = None
        values: list[str | None] = [None] * len(columns)
        for cell in cells:
            c = column_index(cell)
            if c is not None and _is_value(cell.text):
                values[c] = clean(cell.text)
        printed = clean((pending_text + " " + " ".join(s.text for s in [label_seg, *cells])).strip())
        rows.append(TableRow(label=label.lstrip("—–- ").strip(), group=member_of, values=values, text=printed, bbox=_union(boxes)))
    bbox = _union([s.bbox for line in header_lines for s in line.segments] + [r.bbox for r in rows])
    if caption:
        caption_line = lines[k]
        bbox = _union([bbox] + [s.bbox for s in caption_line.segments])
    header_text = " | ".join(header_texts)
    return LeaderTable(page_number, fr_page, caption, header_texts, rows, bbox, header_text)


# --- the rule -------------------------------------------------------------------------------


@dataclass
class Section:
    number: str  # "I"
    title: str  # "Background"
    text: str
    block: Block


@dataclass
class Change:
    """One amendatory change: an instruction, or one of its lettered items."""

    instruction: str  # "2" or "6(a)"
    section: str | None  # FAR section, "22.1503"
    paragraphs: str | None  # "(b)(2)"
    action: str
    previous: str | None
    new: str | None
    text: str
    block: Block
    part: str | None
    record_type: str = "Amendment"
    clause_kind: str | None = None  # "Provision" | "Clause"
    clause_title: str | None = None
    revision_date: str | None = None
    table: LeaderTable | None = None


@dataclass
class FinalRule:
    title: str | None = None  # "Federal Acquisition Regulation: Trade Agreements Thresholds"
    cfr_parts: str | None = None
    reference_line: str | None = None  # "[FAC 2026–01, FAR Case 2025–007; Docket No. …]"
    fac: str | None = None
    far_case: str | None = None
    docket: str | None = None
    rin: str | None = None
    agency: str | None = None
    action: str | None = None
    summary: str | None = None
    dates: str | None = None
    effective_date: str | None = None
    contact: str | None = None
    signed_by: str | None = None
    fr_doc: str | None = None
    volume: str | None = None
    issue: str | None = None
    issue_date: str | None = None
    fr_pages: list[str] = field(default_factory=list)
    companions: list[tuple[str | None, str]] = field(default_factory=list)  # (FR Doc, title)
    sections: list[Section] = field(default_factory=list)
    tables: list[tuple[LeaderTable, str | None, Change | None]] = field(default_factory=list)  # table, context section, instruction
    changes: list[Change] = field(default_factory=list)
    authority: tuple[str, Block] | None = None
    first_block: Block | None = None

    @property
    def fr_citation(self) -> str | None:
        if not self.volume or not self.fr_pages:
            return None
        first, last = self.fr_pages[0], self.fr_pages[-1]
        return f"{self.volume} FR {first}" + (f"–{last}" if last != first else "")


def _documents(blocks: list[Block]) -> list[FrDocument]:
    docs: list[FrDocument] = []
    current: list[Block] = []
    for block in blocks:
        current.append(block)
        match = _FR_DOC.search(block.text)
        if match:
            docs.append(FrDocument(current, match.group("doc")))
            current = []
    if current:
        docs.append(FrDocument(current, None))
    return docs


def _document_title(doc: FrDocument) -> str:
    for index, block in enumerate(doc.blocks):
        if _CAPTION.match(block.text) and block.text.upper().startswith("AGENCY") and index:
            return doc.blocks[index - 1].text
    return doc.blocks[0].text


def read_pdf(pdf) -> tuple[list[Block], dict | None]:
    blocks: list[Block] = []
    header = None
    for index, page in enumerate(pdf):
        page_blocks_, _ = page_blocks(page, index + 1)
        blocks.extend(page_blocks_)
        if header is None:
            header = _header_info(page)[1]
    return blocks, header


def parse_final_rule(pdf) -> FinalRule | None:
    blocks, header = read_pdf(pdf)
    docs = _documents(blocks)
    rule_doc = next((d for d in docs if re.match(r"^final rule\.?$", d.caption("ACTION") or "", re.I)), None)
    if rule_doc is None:
        return None
    rule = FinalRule(fr_doc=rule_doc.fr_doc, first_block=rule_doc.blocks[0])
    if header:
        rule.volume, rule.issue, rule.issue_date = header["vol"], header["no"], clean(header["date"])
    rule.companions = [(d.fr_doc, _document_title(d)) for d in docs if d is not rule_doc and d.fr_doc]
    pages: list[str] = []
    for block in rule_doc.blocks:
        if block.fr_page and block.fr_page not in pages:
            pages.append(block.fr_page)
    rule.fr_pages = pages

    _parse_front_matter(rule, rule_doc)
    _parse_body(rule, rule_doc)
    return rule


def _parse_front_matter(rule: FinalRule, doc: FrDocument) -> None:
    for index, block in enumerate(doc.blocks):
        text = block.text
        if text.startswith("48 CFR"):
            rule.cfr_parts = text
        elif text.startswith("[") and ("FAC" in text or "FAR Case" in text):
            rule.reference_line = text
            if m := re.search(r"FAC\s+(\d{4}[–-]\d{2})", text):
                rule.fac = m.group(1)
            if m := re.search(r"FAR Case\s+(\d{4}[–-]\d{3})", text):
                rule.far_case = m.group(1)
            if m := re.search(r"Docket No\.\s*([\w–-]+)", text):
                rule.docket = m.group(1)
        elif m := re.match(r"^RIN\s+(\S+)$", text):
            rule.rin = m.group(1)
        elif text.upper().startswith("AGENCY:") and index and rule.title is None:
            rule.title = doc.blocks[index - 1].text
    rule.agency = doc.caption("AGENCY")
    rule.action = doc.caption("ACTION")
    rule.summary = doc.caption("SUMMARY")
    rule.dates = doc.caption("DATES")
    rule.contact = doc.caption("FOR FURTHER INFORMATION CONTACT")
    if rule.dates and (m := re.search(r"Effective\s+([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})", rule.dates)):
        rule.effective_date = m.group(1)


def _sentence_end(text: str) -> bool:
    return text.rstrip().endswith((".", ":", ";", "?", "!", ")"))


def _parse_body(rule: FinalRule, doc: FrDocument) -> None:
    blocks = doc.blocks
    start = next((i for i, b in enumerate(blocks) if b.text.upper().startswith("SUPPLEMENTARY INFORMATION")), len(blocks))
    regulatory = next((i for i, b in enumerate(blocks) if re.match(r"^Therefore,.*amend\b", b.text)), len(blocks))
    subjects = next((i for i, b in enumerate(blocks) if b.text.startswith("List of Subjects")), regulatory)

    # Preamble sections (I. Background …), each with its text.
    current: Section | None = None
    for block in blocks[start + 1 : subjects]:
        if block.table is not None:
            rule.tables.append((block.table, f"{current.number}. {current.title}" if current else None, None))
            continue
        match = _ROMAN_SECTION.match(block.text)
        if match and len(block.text) < 230 and not _sentence_end(match.group("title")):
            current = Section(match.group("num"), clean(match.group("title")), "", block)
            rule.sections.append(current)
            continue
        if current is None:
            continue
        if not current.text:
            current.text = block.text
        elif _sentence_end(current.text):
            current.text += "\n" + block.text
        else:  # a paragraph continued in the next column
            current.text += " " + block.text

    # Signature after List of Subjects.
    for block in blocks[subjects:regulatory]:
        if re.match(r"^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+,", block.text):
            rule.signed_by = block.text

    _parse_amendments(rule, blocks[regulatory + 1 :])


def _changes_from(text: str) -> list[tuple[list[str], list[str]]]:
    """Removed/added value pairs: "removing ‘‘X’’ and adding ‘‘Y’’";
    "removing ‘‘A’’ and ‘‘B’’ and adding ‘‘C’’ and ‘‘D’’ …, respectively"."""

    match = re.search(r"\bremov\w*\b(?P<old>.*?)\badd\w*\b(?P<new>.*)", text, re.I | re.S)
    if not match:
        return []
    old = [m.group("value") for m in _QUOTED.finditer(match.group("old"))]
    new = [m.group("value") for m in _QUOTED.finditer(match.group("new"))]
    return [(old, new)] if old or new else []


def _paragraphs(text: str) -> str | None:
    match = _PARAGRAPHS.search(text)
    if not match:
        return None
    return clean(match.group("paras"))


def _parse_amendments(rule: FinalRule, blocks: list[Block]) -> None:
    part: str | None = None
    section: str | None = None
    titles: dict[str, str] = {}
    last_instruction: Change | None = None
    pending_kind: list[Change] = []  # date revisions waiting for "(MAR 2026)"
    expecting_table: Change | None = None
    authority: list[Block] = []
    in_authority = False
    i = 0
    while i < len(blocks):
        block = blocks[i]
        text = block.text
        i += 1
        if _FR_DOC.search(text) or text.startswith("BILLING CODE"):
            break
        if block.table is not None:
            rule.tables.append((block.table, f"{far_number(expecting_table.section)}{expecting_table.paragraphs or ''}" if expecting_table and expecting_table.section else None, expecting_table))
            if expecting_table is not None:
                expecting_table.table = block.table
            expecting_table = None
            continue
        if in_authority:
            if text.startswith(("PART ",) ) or _INSTRUCTION.match(text) or _AMENDED_HEADING.match(text) or block.table is not None:
                in_authority = False
            else:
                authority.append(block)
                continue
        if m := _PART_HEADING.match(text):
            part = text
            continue
        if m := _AMENDED_HEADING.match(text):
            section = m.group("section")
            continue
        if text.startswith("Authority:"):
            authority = [block]
            in_authority = True
            continue
        if m := _SECTION_TITLE.match(text):
            titles[far_number(m.group("section"))] = clean(m.group("title"))
            for change in pending_kind:
                if change.section and far_number(change.section) == far_number(m.group("section")):
                    change.clause_title = clean(m.group("title"))
            continue
        if date := _REVISED_DATE.search(text):
            # "Annual Representations and Certifications (MAR 2026)": the
            # revised heading of the provision/clause being redated.
            for change in pending_kind:
                if change.revision_date is None:
                    change.revision_date = date.group("date")
                    change.new = f"({date.group('date')})"
                    change.text += f"\nRevised heading: {text}"
            pending_kind = [c for c in pending_kind if c.revision_date is None]
            continue
        if text.startswith("*") or text == "The revision reads as follows:":
            continue
        if m := _INSTRUCTION.match(text):
            body = m.group("text")
            number = m.group("num")
            ref = _SECTION_REF.search(body)
            if ref:
                section = ref.group("section")
            if re.search(r"authority citation", body, re.I):
                rule.changes.append(Change(number, None, None, "Authority citation continues", None, None, text, block, part, record_type="Authority"))
                last_instruction = rule.changes[-1]
                continue
            head, *items = _SUB_ITEM.split(body)
            pairs = list(zip(items[0::2], items[1::2])) if items else []
            instruction = Change(number, section, _paragraphs(head), "", None, None, clean(f"■{number}. {head}"), block, part)
            last_instruction = instruction
            if re.search(r"\brevis\w+ table", head, re.I):
                instruction.action = "Revise table"
                instruction.record_type = "Amendment"
                rule.changes.append(instruction)
                expecting_table = instruction
                continue
            if not pairs:
                # "Amend section 52.204–8 by—": its lettered items follow
                # in the next blocks; the lead-in is not a change itself.
                if not re.search(r"\bby\s*[—–-]?\s*$", head.strip()):
                    _add_value_changes(rule, instruction, head)
                continue
            for letter, item in pairs:
                _add_item(rule, instruction, letter, item, block, pending_kind)
            continue
        if (m := re.match(r"^[" + _SQUARE + r"]\s*(?P<letter>[a-z])\.\s*(?P<text>.*)$", text, re.S)) and last_instruction is not None:
            _add_item(rule, last_instruction, m.group("letter"), m.group("text"), block, pending_kind)
            continue
    if authority:
        rule.authority = (join_lines([b.text for b in authority]), authority[0])
    for change in rule.changes:
        if change.section and change.clause_title is None and far_number(change.section) in titles:
            change.clause_title = titles[far_number(change.section)]


def _add_value_changes(rule: FinalRule, instruction: Change, text: str) -> None:
    pairs = _changes_from(text)
    if not pairs:
        instruction.action = "Amend"
        rule.changes.append(instruction)
        return
    old, new = pairs[0]
    for index in range(max(len(old), len(new))):
        rule.changes.append(
            Change(
                instruction.instruction,
                instruction.section,
                instruction.paragraphs or _paragraphs(text),
                "Replace value",
                old[index] if index < len(old) else None,
                new[index] if index < len(new) else None,
                instruction.text,
                instruction.block,
                instruction.part,
            )
        )


def _add_item(rule: FinalRule, instruction: Change, letter: str, item: str, block: Block, pending_kind: list[Change]) -> None:
    item = clean(item).rstrip(";").rstrip()
    item = re.sub(r"\s+and$", "", item)
    label = f"{instruction.instruction}({letter})"
    text = f"{instruction.text}\n■{letter}. {item}"
    if m := re.search(r"Revising the date of the (?P<kind>provision|clause)", item, re.I):
        change = Change(label, instruction.section, None, "Revise date", None, None, text, block, instruction.part,
                        record_type="Date Revision", clause_kind=m.group("kind").capitalize())
        rule.changes.append(change)
        pending_kind.append(change)
        return
    pairs = _changes_from(item)
    if not pairs:
        rule.changes.append(Change(label, instruction.section, _paragraphs(item), "Amend", None, None, text, block, instruction.part))
        return
    old, new = pairs[0]
    for index in range(max(len(old), len(new))):
        rule.changes.append(
            Change(
                label,
                instruction.section,
                _paragraphs(item),
                "Replace value",
                old[index] if index < len(old) else None,
                new[index] if index < len(new) else None,
                text,
                block,
                instruction.part,
            )
        )
