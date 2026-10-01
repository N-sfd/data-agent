"""Schedule tables (line items / CLINs, delivery information) read from
their printed header row: columns keep the source's own headings ("MAX
QUANTITY", "Unit Price", "DODAAC / CAGE") and map to canonical keys
(quantity, unit_price, dodaac_cage).

Records start at an item number in the first column and run to the
largest vertical gap before the next one; a table continues across pages
that repeat its header, and repeated headers are never data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.contract_structure.lines import PageLines, Word, compact

LINE_ITEMS = "line_items"
DELIVERY = "delivery_information"

# (compact header phrase, canonical key) — longest phrases first.
_LINE_ITEM_VOCAB = (
    ("itemno.", "item_number"), ("itemno", "item_number"), ("item", "item_number"), ("clin", "item_number"),
    ("supplies/services", "description"), ("supplies/service", "description"), ("suppliesorservices", "description"),
    ("description", "description"),
    ("maxquantity", "quantity"), ("quantity", "quantity"), ("qty", "quantity"),
    ("unitprice", "unit_price"), ("unit", "unit"),
    ("maxamount", "amount"), ("totalamount", "amount"), ("amount", "amount"),
)
_DELIVERY_VOCAB = (
    ("clin", "clin"), ("lineitem", "clin"), ("itemno.", "clin"), ("itemno", "clin"),
    ("deliverydate", "delivery_date"), ("deliveryschedule", "delivery_date"),
    ("quantity", "quantity"),
    ("shiptoaddress", "ship_to"), ("addressandpoc", "ship_to"), ("shipto", "ship_to"),
    ("dodaac/cage", "dodaac_cage"), ("dodaac", "dodaac_cage"),
)
_TEXT_COLUMNS = {"description", "ship_to"}
_NUMERIC_COLUMNS = {"quantity", "unit", "unit_price", "amount"}
_ITEM_NUMBER = re.compile(r"^\d{4,6}[A-Z]{0,2}$")
_MONEY = re.compile(r"(USD|\$)\s?[\d,]+(\.\d+)?|^[\d,]+\.\d{2}$")
# Lines that end a table on its page.
_TERMINATOR = re.compile(
    r"^(section\s+[a-m]\b|delivery\s+information$|inspection\s+and\s+acceptance|clauses\s+incorporated)",
    re.IGNORECASE,
)
# Per-page totals printed under a CLIN ("MAX $600,000,000.00", "NET AMT").
_PAGE_TOTAL = re.compile(
    r"^((max|net\s*amt|total(\s+(price|amount))?)\s*)+([$]?[\d,]+(\.\d+)?)?$", re.IGNORECASE
)
_PHRASE_GAP = 8.0


@dataclass
class Column:
    key: str
    header: str
    x0: float
    x1: float
    left: float = 0.0
    right: float = 0.0


@dataclass
class TableRecord:
    kind: str
    values: dict[str, str]
    page: int
    bbox: tuple[float, float, float, float]
    evidence: str
    cell_boxes: dict[str, tuple[int, tuple[float, float, float, float]]] = field(default_factory=dict)


@dataclass
class Table:
    kind: str
    columns: list[Column]
    records: list[TableRecord]
    # Item numbers printed in the middle of their text block (FA30): records
    # split at the midpoint between item rows instead of at the next one.
    centered: bool | None = None
    # Centred layout: text at the foot of a page that starts the next
    # page's first item (its y shifted above that page's top).
    pending: list[list[Word]] = field(default_factory=list)


def _rows(words: list[Word], tolerance: float = 3.0) -> list[list[Word]]:
    rows: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w.y0, w.x0)):
        if rows and abs(word.y0 - rows[-1][0].y0) <= tolerance:
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda w: w.x0) for row in rows]


def _match_header(row: list[Word], stacked: list[list[Word]], vocab) -> list[Column] | None:
    # Fold stacked header words ("MAX" over "QUANTITY", "DODAAC /" over
    # "CAGE") into the word above them; drop column letters "(A)".
    tokens = [[word] for word in row]
    for extra in stacked:
        for word in extra:
            if re.fullmatch(r"\([A-Z]\)", word.text):
                continue
            host = next(
                (token for token in tokens if token[0].x0 - 4 <= (word.x0 + word.x1) / 2 <= token[-1].x1 + 30
                 and min(t.x1 for t in token) >= word.x0 - 30),
                None,
            )
            if host is not None:
                host.append(word)
    columns: list[Column] = []
    i = 0
    while i < len(tokens):
        for span in (3, 2, 1):
            group = tokens[i:i + span]
            if len(group) < span:
                continue
            words = [w for token in group for w in token]
            key_text = compact("".join(w.text for w in sorted(words, key=lambda w: (round(w.y0), w.x0))))
            hit = next((key for phrase, key in vocab if key_text == phrase), None)
            if hit:
                ordered = sorted(words, key=lambda w: (round(w.y0), w.x0))
                header = " ".join(w.text for w in ordered).replace(" / ", " / ")
                columns.append(Column(hit, header, min(w.x0 for w in words), max(w.x1 for w in words)))
                i += span
                break
        else:
            i += 1
    keys = [column.key for column in columns]
    if len(set(keys)) != len(keys):
        return None
    return columns


def _find_header(rows: list[list[Word]], index: int) -> tuple[str, list[Column], int] | None:
    row = rows[index]
    text = compact(" ".join(word.text for word in row))
    stacked = [r for r in rows[index + 1:index + 3] if r[0].y0 - row[0].y0 <= 16]
    if ("supplies/service" in text or "suppliesorservices" in text) and ("amount" in text or "quantity" in text):
        columns = _match_header(row, stacked, _LINE_ITEM_VOCAB)
        if columns and columns[0].key == "item_number" and len(columns) >= 4:
            return LINE_ITEMS, columns, len(stacked)
    if ("clin" in text or "lineitem" in text) and ("deliverydate" in text or "deliveryschedule" in text):
        columns = _match_header(row, stacked, _DELIVERY_VOCAB)
        if columns and columns[0].key == "clin" and len(columns) >= 3:
            return DELIVERY, columns, len(stacked)
    return None


def _bound(columns: list[Column], page_width: float) -> None:
    for index, column in enumerate(columns):
        column.left = 0.0 if index == 0 else (columns[index - 1].x1 + column.x0) / 2
        column.right = page_width if index == len(columns) - 1 else (column.x1 + columns[index + 1].x0) / 2
    # The first column hugs the left margin; item numbers may start a bit left.
    columns[0].left = 0.0


def _column_of(columns: list[Column], word: Word) -> Column:
    centre = (word.x0 + word.x1) / 2
    return next((c for c in columns if c.left <= centre < c.right), columns[-1])


def _phrases(row: list[Word]) -> list[list[Word]]:
    """Words of a row grouped into phrases (normal word spacing); a gap
    wider than _PHRASE_GAP starts a new phrase (a new table cell)."""
    phrases: list[list[Word]] = []
    for word in row:
        if phrases and word.x0 - phrases[-1][-1].x1 <= _PHRASE_GAP:
            phrases[-1].append(word)
        else:
            phrases.append([word])
    return phrases


def _phrase_column(columns: list[Column], phrase: list[Word]) -> Column:
    """Left-aligned text (descriptions, addresses) belongs to the column it
    starts in, even when it runs on across the next columns; anything else
    goes by its centre."""
    start = phrase[0].x0
    for column in columns:
        if column.key in _TEXT_COLUMNS and column.left - 2 <= start < column.right:
            return column
    centre = (phrase[0].x0 + phrase[-1].x1) / 2
    return next((c for c in columns if c.left <= centre < c.right), columns[-1])


def _is_item_start(columns: list[Column], row: list[Word]) -> bool:
    """A record starts where the item column holds a standalone item number
    left-aligned with its heading ("0001", "10300", "0001AA")."""
    first = columns[0]
    for phrase in _phrases(row):
        if len(phrase) == 1 and _ITEM_NUMBER.match(phrase[0].text) and abs(phrase[0].x0 - first.x0) <= 8:
            return True
    return False


@dataclass
class _Block:
    page: int
    rows: list[list[Word]]


def _assemble(kind: str, columns: list[Column], block: _Block) -> TableRecord:
    first_key = columns[0].key
    text_column = next((c for c in columns if c.key in _TEXT_COLUMNS), None)
    item_row_index = next((i for i, row in enumerate(block.rows) if _is_item_start(columns, row)), 0)
    cells: dict[str, list[tuple[float, str, list[Word]]]] = {column.key: [] for column in columns}
    for index, row in enumerate(block.rows):
        if _PAGE_TOTAL.match(" ".join(word.text for word in row).strip()):
            continue
        for phrase in _phrases(row):
            column = _phrase_column(columns, phrase)
            text = " ".join(word.text for word in phrase)
            if column.key == first_key:
                if index == item_row_index and len(phrase) == 1 and _ITEM_NUMBER.match(text) and not cells[first_key]:
                    cells[first_key].append((phrase[0].y0, text, phrase))
                    continue
                # "OPTION" printed under the item number reads with its text.
                if kind == LINE_ITEMS and text_column is not None:
                    column = text_column
            cells[column.key].append((phrase[0].y0, text, phrase))

    values: dict[str, str] = {}
    boxes: dict[str, tuple[int, tuple[float, float, float, float]]] = {}
    item_y = block.rows[item_row_index][0].y0
    for column in columns:
        entries = cells[column.key]
        if not entries:
            continue
        if column.key in _NUMERIC_COLUMNS and kind == LINE_ITEMS:
            # One value per numeric column: on the item row, else the nearest
            # value-looking text in the column (FA30 centres the CLIN number).
            on_row = [e for e in entries if abs(e[0] - item_y) <= 4]
            if on_row:
                entries = on_row
            else:
                numeric = [e for e in entries if _MONEY.search(e[1]) or re.fullmatch(r"[\d,.]+", e[1])]
                pool = numeric or entries
                entries = [min(pool, key=lambda e: abs(e[0] - item_y))]
        grouped: dict[int, list] = {}
        for entry in entries:
            grouped.setdefault(round(entry[0]), []).append(entry)
        joiner = "\n" if column.key in _TEXT_COLUMNS else " "
        value = joiner.join(
            " ".join(e[1] for e in sorted(group, key=lambda e: e[2][0].x0)) for _, group in sorted(grouped.items())
        )
        values[column.key] = value.strip()
        used = [w for e in entries for w in e[2]]
        boxes[column.key] = (
            block.page,
            (min(w.x0 for w in used), min(w.y0 for w in used), max(w.x1 for w in used), max(w.y1 for w in used)),
        )
    all_words = [w for row in block.rows for w in row]
    return TableRecord(
        kind=kind,
        values=values,
        page=block.page,
        bbox=(min(w.x0 for w in all_words), min(w.y0 for w in all_words), max(w.x1 for w in all_words), max(w.y1 for w in all_words)),
        evidence="\n".join(" ".join(w.text for w in row) for row in block.rows)[:4000],
        cell_boxes=boxes,
    )


def _gap(rows: list[list[Word]], i: int) -> float:
    return rows[i][0].y0 - max(w.y1 for w in rows[i - 1])


def _typical_gap(rows: list[list[Word]]) -> float:
    gaps = sorted(_gap(rows, i) for i in range(1, len(rows)))
    return gaps[len(gaps) // 2] if gaps else 3.0


def _clear_gap(rows: list[list[Word]], low: int, high: int, typical: float) -> int | None:
    """The row after the widest vertical gap in rows[low..high], when it
    clearly exceeds normal line spacing; None when the rows run together."""
    if high - low < 1:
        return None
    widest, at = max(((_gap(rows, i), i) for i in range(low + 1, high + 1)), key=lambda gap: gap[0])
    return at if widest > max(6.0, typical * 1.8) else None


def _split_blocks(
    rows: list[list[Word]], starts: list[int], first: int, typical: float, centered: bool = False
) -> list[tuple[int, int]]:
    """Each record ends at the clear gap before the next item row, else at
    it; in a centred layout, at the midpoint between the two item rows."""
    bounds = [first]
    for n in range(len(starts) - 1):
        if centered:
            middle = (rows[starts[n]][0].y0 + rows[starts[n + 1]][0].y0) / 2
            bounds.append(next(i for i in range(starts[n] + 1, starts[n + 1] + 1) if rows[i][0].y0 > middle))
            continue
        gap = _clear_gap(rows, starts[n], starts[n + 1], typical)
        bounds.append(gap if gap is not None else starts[n + 1])
    bounds.append(len(rows))
    return [(bounds[n], bounds[n + 1]) for n in range(len(starts))]


def _read_body(table: Table, columns: list[Column], page: PageLines, body: list[list[Word]], kind: str) -> None:
    body = [row for row in body if not re.fullmatch(r"continued\s*\.*", compact(" ".join(w.text for w in row)))]
    carried = len(table.pending)
    if carried:
        body = [*table.pending, *body]
        table.pending = []
    starts = [i for i, row in enumerate(body) if _is_item_start(columns, row)]
    if not starts:
        return
    typical = _typical_gap(body[carried:] or body)
    # Rows above the first item: up to a clear gap they are this item's own
    # text (a centred CLIN); before it, the previous page's record
    # continuing, or a preamble (delivery location, notes).
    gap = _clear_gap(body, carried, starts[0], typical) if starts[0] > carried else None
    first = gap if gap is not None else 0
    if carried and gap is None:
        first = 0  # the carried rows open this page's first item
    if table.centered is None and not table.records:
        # Text running into the first item from above it: a centred layout.
        table.centered = first < starts[0] and kind == LINE_ITEMS
    lead = body[:first]
    # Only a line-item description runs on across a page break; delivery
    # rows are cell-by-cell and their leftovers are not guessed into a column.
    if lead and kind == LINE_ITEMS and table.records and table.records[-1].page == page.page_number - 1:
        previous = table.records[-1]
        text = "\n".join(" ".join(w.text for w in row) for row in lead)
        key = next((c.key for c in columns if c.key in _TEXT_COLUMNS), None)
        if key:
            previous.values[key] = (previous.values.get(key, "") + "\n" + text).strip()
        previous.evidence += "\n" + text
    end = len(body)
    if table.centered:
        # The last item on a page ends at its clear gap; what follows opens
        # the first item on the next page (shifted above that page's top).
        tail = _clear_gap(body, starts[-1], len(body) - 1, typical) if len(body) - 1 > starts[-1] else None
        if tail is not None:
            end = tail
        table.pending = [
            [Word(w.text, w.x0, w.y0 - page.height, w.x1, w.y1 - page.height) for w in row] for row in body[end:]
        ]
    for start, stop in _split_blocks(body[:end], starts, first, typical, bool(table.centered)):
        table.records.append(_assemble(kind, columns, _Block(page.page_number, body[start:stop])))


def _body_end(rows: list[list[Word]], start: int) -> tuple[int, bool]:
    """(end row, whether the table stops on this page)."""
    end = start
    while end < len(rows):
        text = " ".join(word.text for word in rows[end]).strip()
        if _TERMINATOR.match(text) or _find_header(rows, end):
            return end, bool(_TERMINATOR.match(text))
        end += 1
    return end, False


def read_schedule_tables(pages: list[PageLines]) -> list[Table]:
    tables: dict[str, Table] = {}
    # A table whose header printed only on its first page continues on the
    # following pages until a section heading ends it (FA30 Section B).
    active: tuple[str, list[Column]] | None = None
    for page in pages:
        rows = _rows(list(page.words))
        index = 0
        if active is not None and not any(_find_header(rows, i) for i in range(len(rows))):
            kind, columns = active
            end, stopped = _body_end(rows, 0)
            if any(_is_item_start(columns, row) for row in rows[:end]) or not stopped:
                _read_body(tables[kind], columns, page, rows[:end], kind)
            if stopped:
                active = None
                tables[kind].pending = []
            continue
        while index < len(rows):
            header = _find_header(rows, index)
            if not header:
                index += 1
                continue
            kind, columns, stacked = header
            _bound(columns, page.width)
            table = tables.get(kind)
            if table is None:
                table = tables[kind] = Table(kind, columns, [])
            body_start = index + 1 + stacked
            body_end, stopped = _body_end(rows, body_start)
            _read_body(table, columns, page, rows[body_start:body_end], kind)
            active = None if stopped else (kind, columns)
            if stopped:
                table.pending = []
            index = body_end
    return [table for table in tables.values() if table.records]
