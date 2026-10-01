"""The contract body in Uniform Contract Format: sections ("SECTION B -
SUPPLIES OR SERVICES AND PRICES/COSTS"), their numbered subsections ("B.1
GENERAL", "C.2.1.1 …") with full text, the tables printed inside them
under their own column headings, and the Section J attachment list.

A subsection heading is a line of its own whose letter matches the
section it is in — a deliverables table row citing "G.3.1.1" inside
Section F is table content, not a heading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from app.contract_structure.lines import PageLines, Word, compact, join_paragraphs
from app.services.line_model import LogicalLine

_SECTION = re.compile(r"^SECTION\s+(?P<letter>[A-M])\s*[-–]\s*(?P<title>\S.*)$", re.IGNORECASE)
_SUBSECTION = re.compile(r"^(?P<letter>[A-M])\.(?P<rest>\d+(?:\.\d+)*)\s+(?P<title>\S.*)$")
_END_OF_SECTION = re.compile(r"^\(End of Section [A-M]\)$", re.IGNORECASE)
_ATTACHMENT = re.compile(
    r"^(?P<ref>J\.?[A-Z]?-\d+[A-Z]?|Attachment\s+[A-Z0-9-]+|Exhibit\s+[A-Z0-9-]+)\s+(?P<title>\S.*)$",
    re.IGNORECASE,
)
_PHRASE_GAP = 12.0
# Header rows that other readers own (schedule tables, clause lists).
_OWNED_HEADER = re.compile(
    r"supplies/service|suppliesorservices|deliverydate|deliveryschedule|^number.*title|title.*date"
    r"|effective|alternate|variation|deviation|lineitem"
)
_CONNECTOR_END = re.compile(r"(,|\b(and|or|of|the|to|for|in|with))$", re.IGNORECASE)


@dataclass
class Subsection:
    section: str
    number: str
    title: str
    text: str
    page: int
    bbox: tuple[float, float, float, float]


@dataclass
class BodyTable:
    table_id: str
    section: str
    subsection: str | None
    headers: list[str]
    rows: list[list[str]]
    pages: list[int]
    row_boxes: list[tuple[int, tuple[float, float, float, float]]] = field(default_factory=list)


@dataclass
class Attachment:
    section: str
    group: str | None
    reference: str
    title: str
    page: int
    bbox: tuple[float, float, float, float]


@dataclass
class ContractBody:
    sections: list[dict]
    subsections: list[Subsection]
    tables: list[BodyTable]
    attachments: list[Attachment]


@dataclass
class _Row:
    page: int
    lines: list[LogicalLine]
    phrases: list[list[Word]]

    @property
    def text(self) -> str:
        return "  ".join(line.text.strip() for line in self.lines)

    @property
    def y0(self) -> float:
        return min(line.y0 for line in self.lines)

    @property
    def y1(self) -> float:
        return max(line.y1 for line in self.lines)


def _rows(page: PageLines) -> list[_Row]:
    grouped: list[list[LogicalLine]] = []
    for line in sorted(page.lines, key=lambda line: (line.y0, line.x0)):
        if grouped and abs(line.y0 - grouped[-1][0].y0) <= 2.5:
            grouped[-1].append(line)
        else:
            grouped.append([line])
    # Each word joins the one row whose top it shares.
    by_row: list[list[Word]] = [[] for _ in grouped]
    tops = [lines[0].y0 for lines in grouped]
    for word in page.words:
        if not tops:
            break
        nearest = min(range(len(tops)), key=lambda i: abs(tops[i] - word.y0))
        if abs(tops[nearest] - word.y0) <= 3:
            by_row[nearest].append(word)
    rows: list[_Row] = []
    for lines, words in zip(grouped, by_row):
        lines.sort(key=lambda line: line.x0)
        phrases: list[list[Word]] = []
        for word in sorted(words, key=lambda w: w.x0):
            if phrases and word.x0 - phrases[-1][-1].x1 <= _PHRASE_GAP:
                phrases[-1].append(word)
            else:
                phrases.append([word])
        rows.append(_Row(page.page_number, lines, phrases))
    return rows


def _phrase_text(phrase: list[Word]) -> str:
    return " ".join(word.text for word in phrase)


def _is_toc(rows: list[_Row]) -> bool:
    return sum(1 for row in rows if re.search(r"\.{5,}", row.text)) >= 5


def _label_like(row: _Row) -> bool:
    labels = [_phrase_text(p) for p in row.phrases]
    return bool(labels) and all(
        len(label.split()) <= 5
        and not re.search(r"\d", label)
        and label[:1].isupper()
        and not _CONNECTOR_END.search(label)
        for label in labels
    )


def _header_block(rows: list[_Row], index: int) -> tuple[list[tuple[str, float, float]], set[int]] | None:
    """A body-table header: a row of three or more short, label-like
    phrases, together with label rows stacked just above/below it
    ("Reference" / "Identifier"). Returns columns and the rows used."""
    row = rows[index]
    if len(row.phrases) < 2 or not _label_like(row):
        return None
    block = {index}
    for j in (index - 1, index + 1, index + 2):
        if 0 <= j < len(rows) and abs(rows[j].y0 - row.y0) <= 16 and _label_like(rows[j]):
            block.add(j)
    phrases = [p for j in sorted(block) for p in rows[j].phrases]
    if _OWNED_HEADER.search(compact(" ".join(_phrase_text(p) for p in phrases))):
        return None
    columns: list[list[list[Word]]] = []
    for phrase in sorted(phrases, key=lambda p: p[0].x0):
        host = next((c for c in columns if abs(c[0][0].x0 - phrase[0].x0) <= 12), None)
        if host is None:
            columns.append([phrase])
        else:
            host.append(phrase)
    if len(columns) < 3:
        return None
    labelled = [
        (" ".join(_phrase_text(p) for p in sorted(column, key=lambda p: p[0].y0)),
         min(p[0].x0 for p in column), max(p[-1].x1 for p in column))
        for column in columns
    ]
    return labelled, block


def _column_starts(columns: list[tuple[str, float, float]], following: list[_Row]) -> list[float]:
    """Where each column's data begins. Headings are often centred over a
    left-aligned column, so the data's own recurring left edges decide;
    each heading takes the nearest edge at or left of it."""
    edges: dict[int, int] = {}
    for row in following:
        words = [w for phrase in row.phrases for w in phrase]
        for i, word in enumerate(words):
            if i == 0 or word.x0 - words[i - 1].x1 > 6:
                key = round(word.x0 / 2)
                edges[key] = edges.get(key, 0) + 1
    recurring = sorted(key * 2 for key, count in edges.items() if count >= 2)
    starts: list[float] = []
    for label, x0, x1 in columns:
        floor = starts[-1] + 4 if starts else -1e9
        candidates = [edge for edge in recurring if floor < edge <= x0 + 2]
        starts.append(max(candidates) if candidates else x0)
    return starts


def _column_index(starts: list[float], word: Word) -> int:
    """A left-aligned cell's words belong to the column they start in."""
    index = 0
    for i, start in enumerate(starts):
        if word.x0 >= start - 3:
            index = i
    return index


def _aligned(starts: list[float], row: _Row) -> bool:
    """Does a row's cell layout line up with an open table's columns?"""
    words = [w for phrase in row.phrases for w in phrase]
    lefts = [w.x0 for i, w in enumerate(words) if i == 0 or w.x0 - words[i - 1].x1 > 6]
    hits = sum(1 for x in lefts if any(abs(x - start) <= 4 for start in starts))
    return len(lefts) >= 2 and hits >= 2


def read_contract_body(pages: list[PageLines], skip_table_pages: set[int] | None = None) -> ContractBody:
    """`skip_table_pages`: pages whose tables another reader owns (the
    line-item schedule)."""
    skip_table_pages = skip_table_pages or set()
    sections: list[dict] = []
    subsections: list[Subsection] = []
    tables: list[BodyTable] = []
    attachments: list[Attachment] = []

    section: dict | None = None
    current: Subsection | None = None
    body: list[LogicalLine] = []
    table: BodyTable | None = None
    table_columns: list[float] | None = None
    table_cells: list[list[str]] | None = None
    attachment_group: str | None = None
    header_bottom = 0.0
    last_bottom, last_page = 0.0, 0

    def close_subsection() -> None:
        nonlocal current, body
        if current is not None:
            current.text = join_paragraphs(body).strip()
            subsections.append(current)
        current, body = None, []

    def close_table() -> None:
        nonlocal table, table_columns, table_cells
        if table is not None and table.rows:
            # A blank form-fill ("____") inside a clause is not a data table.
            meaningful = sum(1 for cells in table.rows if sum(1 for c in cells if re.search(r"[A-Za-z0-9]", c)) >= 2)
            if meaningful * 2 >= len(table.rows):
                tables.append(table)
        table, table_columns, table_cells = None, None, None

    for page in pages:
        rows = _rows(page)
        header_rows: set[int] = set()
        if _is_toc(rows):
            continue
        for row_index, row in enumerate(rows):
            text = row.text.strip()
            first = row.lines[0].text.strip()
            heading = _SECTION.match(first) if len(row.lines) <= 2 else None
            if heading and not re.search(r"\.{5,}", text):
                close_table()
                close_subsection()
                title = re.sub(r"\s{2,}", " ", first)
                section = {"letter": heading.group("letter").upper(), "heading": title, "page": page.page_number}
                sections.append(section)
                attachment_group = None
                continue
            if section is None:
                continue
            if _END_OF_SECTION.match(text):
                close_table()
                close_subsection()
                section = None
                continue

            sub = _SUBSECTION.match(first)
            if (
                sub
                and sub.group("letter") == section["letter"]
                and len(row.phrases) <= 2
                and len(sub.group("title")) <= 140
            ):
                close_table()
                close_subsection()
                number = f"{sub.group('letter')}.{sub.group('rest')}"
                title = re.sub(r"\s{2,}", " ", text[len(number):]).strip()
                current = Subsection(
                    section["heading"], number, title, "", page.page_number,
                    (min(l.x0 for l in row.lines), row.y0, max(l.x1 for l in row.lines), row.y1),
                )
                attachment_group = f"{number} {title}" if section["letter"] == "J" else attachment_group
                continue

            if section["letter"] == "J":
                hit = _ATTACHMENT.match(re.sub(r"\s{2,}", " ", text))
                if hit:
                    attachments.append(
                        Attachment(section["heading"], attachment_group, hit.group("ref"),
                                   hit.group("title").strip(), page.page_number,
                                   (min(l.x0 for l in row.lines), row.y0, max(l.x1 for l in row.lines), row.y1))
                    )
                    continue
                if attachments and attachments[-1].page == page.page_number and row.lines[0].x0 > 40 and len(row.phrases) == 1 \
                        and row.y0 - attachments[-1].bbox[3] < 14 and not text.startswith("("):
                    attachments[-1].title += " " + text  # wrapped attachment title
                    continue

            if row_index in header_rows:
                continue  # a stacked heading line already read into the header
            continuing = table is not None and table_columns is not None and _aligned(table_columns, row)
            found = None if continuing or page.page_number in skip_table_pages else _header_block(rows, row_index)
            columns = found[0] if found else None
            if found:
                header_rows = {j for j in found[1] if j > row_index}
                close_table()
                table_columns = _column_starts(columns, rows[row_index + 1:row_index + 12])
                header_bottom = row.y1
                last_bottom, last_page = max(rows[j].y1 for j in found[1]), page.page_number
                table = BodyTable(
                    table_id=f"{section['letter']}:{len(tables) + 1}:{page.page_number}",
                    section=section["heading"],
                    subsection=f"{current.number} {current.title}" if current else None,
                    headers=[label for label, _, _ in columns],
                    rows=[],
                    pages=[page.page_number],
                )
                table_cells = None
                continue

            if table is not None and table_columns is not None:
                spans_prose = len(row.phrases) == 1 and (row.phrases[0][-1].x1 - row.phrases[0][0].x0) > 0.6 * page.width
                clause_boundary = bool(re.match(r"^\d{0,2}52\.\d{3}-\d+\s", text)) or "(End of clause)" in text
                if spans_prose or clause_boundary:
                    close_table()
                else:
                    # Word by word: body-table columns sit close together.
                    cells = [""] * len(table_columns)
                    for word in (w for phrase in row.phrases for w in phrase):
                        index = _column_index(table_columns, word)
                        cells[index] = (cells[index] + " " + word.text).strip()
                    filled = [i for i, cell in enumerate(cells) if cell]
                    # A new record: an identifier row while the current one
                    # already has its own, or a clear blank gap (FA30 centres
                    # the number on a multi-line row).
                    gap = row.y0 - last_bottom if last_page == page.page_number else 0.0
                    has_id = table_cells is not None and bool(table_cells[0])
                    starts_record = (bool(cells[0]) and len(filled) >= 2 and (has_id or table_cells is None)) or (
                        gap > 8 and table_cells is not None
                    )
                    if table_cells is not None and not has_id and cells[0] and not starts_record:
                        pass
                    if starts_record or table_cells is None:
                        table_cells = cells
                        table.rows.append(table_cells)
                        table.row_boxes.append(
                            (page.page_number, (min(l.x0 for l in row.lines), row.y0, max(l.x1 for l in row.lines), row.y1))
                        )
                    else:
                        for i, cell in enumerate(cells):
                            if cell:
                                table_cells[i] = (table_cells[i] + "\n" + cell).strip()
                    if page.page_number not in table.pages:
                        table.pages.append(page.page_number)
                    last_bottom, last_page = row.y1, page.page_number
                    continue

            if current is not None:
                body.append(row.lines[0] if len(row.lines) == 1 else replace(row.lines[0], text=text, x1=max(l.x1 for l in row.lines)))
    close_table()
    close_subsection()
    return ContractBody(sections, subsections, tables, attachments)
