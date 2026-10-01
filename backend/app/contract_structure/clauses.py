"""Contract clauses with their incorporation context.

Structural headings ("CLAUSES INCORPORATED BY REFERENCE", "DFARS Clauses
Incorporated by Full Text", "I.2.4 FAR and GSAM/R Clauses in Full Text")
set the context for every clause below them until another structural or
section heading changes it. Reference sections are clause lists (number /
title / date rows, read by layout); full-text sections are clause headings
followed by their complete text. A clause cited in narrative outside such
a context is not a clause record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.contract_structure.lines import PageLines, Word, compact, join_paragraphs
from app.services.line_model import LogicalLine

BY_REFERENCE = "Incorporated by Reference"
IN_FULL_TEXT = "Incorporated in Full Text"

_NUMBER = r"\d{0,2}52\.\d{3}-\d{1,5}"
_CLAUSE_START = re.compile(rf"^(?P<number>{_NUMBER})(?P<dev>\s*\(Dev\))?\b")
_MONTH = r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)[A-Z]*\.?"
_DATE_ONLY = re.compile(rf"^\(?{_MONTH}\s+\d{{4}}\)?$", re.IGNORECASE)
_TRAILING_DATE = re.compile(rf"\s*\(({_MONTH}\s+\d{{4}})\)\s*\.?\s*$", re.IGNORECASE)
_ALTERNATE = re.compile(r"\s*-?\s*(Alternate\s+[IVX]+)\s*(\(([^)]*)\))?\s*$", re.IGNORECASE)
_DEVIATION = re.compile(r"\(DEVIATION[^)]*\)|\(Dev\)", re.IGNORECASE)
# Alternate / deviation column values ("Deviation 2022-O0001 Oct 2021").
_COLUMN_VALUE = re.compile(
    rf"(Alternate\s+[IVX]+|Deviation(\s+[A-Z0-9-]+)?)(\s+\(?({_MONTH}\s+\d{{4}})\)?)?",
    re.IGNORECASE,
)
_INCORPORATION = re.compile(r"(clauses?|provisions?)(andprovisions?|andclauses?)?(incorporated)?(by|in)(reference|fulltext)")
_SECTION_HEADING = re.compile(
    r"^(section\s+[a-m]\s*[-–]|section\s+\d{2}\s?\d{2}\s?\d{2}\b|part\s+[ivx]+\s*[-–]|list\s+of\s+attachments)",
    re.IGNORECASE,
)
_OUTLINE = re.compile(r"^[A-M]\.\d+(\.\d+)*\s+\S")
_OUTLINE_CLAUSE = re.compile(
    rf"^(?:[A-M]\.\d+(?:\.\d+)*\s+)?(?:(?:FAR|DFARS|GSAR|GSAM/R|GSAM|AFFARS)\s+)?(?={_NUMBER}\b)"
)
_TOC_LEADER = re.compile(r"\.{5,}|\s\d{1,3}$")
_REGULATION_HINTS = (
    ("dfars", "DFARS"), ("affars", "AFFARS"), ("gsam", "GSAM/R"), ("gsar", "GSAM/R"),
    ("supplemental", "Supplemental"), ("far", "FAR"),
)
_PREFIX_REGULATION = (
    ("252.", "DFARS"), ("5352.", "AFFARS"), ("5252.", "NMCARS"), ("552.", "GSAM/R"),
    ("1852.", "NFS"), ("3052.", "HSAR"), ("52.", "FAR"),
)


@dataclass
class ClauseRecord:
    clause_number: str
    title: str
    date: str | None
    alternate: str | None
    regulation: str
    incorporation_type: str
    page: int
    bbox: tuple[float, float, float, float]
    evidence: str
    source_heading: str
    text: str | None = None
    end_page: int | None = None


@dataclass
class _Context:
    incorporation: str
    hint: str | None
    heading: str


def _dedupe_parts(parts: list[str | None]) -> str | None:
    """'Deviation 2021-O0008' and '(DEVIATION 2021-O0008)' are one note."""
    kept: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        key = re.sub(r"[^a-z0-9]", "", part.lower())
        if key and key not in seen:
            seen.add(key)
            kept.append(part.strip())
    return "; ".join(kept) or None


def _regulation(number: str, hint: str | None) -> str:
    for prefix, name in _PREFIX_REGULATION:
        if number.startswith(prefix):
            return name
    return hint or "Other"


def incorporation_heading(text: str) -> _Context | None:
    """A structural heading that sets the incorporation context, or None.
    A clause's own heading ("52.252-2 CLAUSES INCORPORATED BY REFERENCE
    (FEB 1998)") is not one; an outline-numbered heading that names the
    clause ("I.2.1 FAR 52.252-2 Clauses Incorporated by Reference (Feb
    1998)") is."""
    stripped = text.strip()
    if len(stripped) > 130 or _TOC_LEADER.search(stripped):
        return None
    outline = bool(_OUTLINE.match(stripped))
    if _CLAUSE_START.match(stripped) or (_TRAILING_DATE.search(stripped) and not outline):
        return None
    key = compact(stripped)
    match = _INCORPORATION.search(key)
    if not match or len(key) - match.end() > 12:
        return None
    incorporation = BY_REFERENCE if match.group(5) == "reference" else IN_FULL_TEXT
    prefix = key[: match.start()]
    hint = next((name for token, name in _REGULATION_HINTS if token in prefix), None)
    return _Context(incorporation, hint, stripped)


def _row_groups(words: list[Word]) -> list[list[list[Word]]]:
    """Rows (y-bands) of phrases."""
    rows: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w.y0, w.x0)):
        if rows and abs(word.y0 - rows[-1][0].y0) <= 2.5:
            rows[-1].append(word)
        else:
            rows.append([word])
    grouped: list[list[list[Word]]] = []
    for row in rows:
        phrases: list[list[Word]] = []
        for word in sorted(row, key=lambda w: w.x0):
            if phrases and word.x0 - phrases[-1][-1].x1 <= 8:
                phrases[-1].append(word)
            else:
                phrases.append([word])
        grouped.append(phrases)
    return grouped


def _text(phrase: list[Word]) -> str:
    return " ".join(word.text for word in phrase)


def _clean_title(title: str) -> tuple[str, str | None, str | None]:
    """(title, date, alternate) from a title that may carry "(JUN 2020)" and
    "- Alternate I (NOV 2021)" (GSA lists)."""
    title = re.sub(r"\s+", " ", title).strip()
    alternate = None
    date = None
    alt = re.search(rf"\s*-\s*(Alternate\s+[IVX]+)\s*(\({_MONTH}\s+\d{{4}}\))?\s*\.?\s*$", title, re.IGNORECASE)
    if alt:
        alternate = alt.group(1) + (f" {alt.group(2)}" if alt.group(2) else "")
        title = title[: alt.start()].strip()
    trailing = _TRAILING_DATE.search(title)
    if trailing:
        date = trailing.group(1)
        title = title[: trailing.start()].strip()
    # A date still inside the title ("... (Sep 2021) Deviation 2021-O0008"):
    # the title ends there; what follows is deviation/alternate text.
    middle = re.search(rf"\(({_MONTH}\s+\d{{4}})\)", title, re.IGNORECASE)
    if middle:
        date = date or middle.group(1)
        tail = title[middle.end():].strip(" .")
        title = title[: middle.start()].strip()
        if tail:
            alternate = "; ".join(part for part in (alternate, tail) if part)
    return title.rstrip(" .").strip(), date, alternate


def _split_trailing_date(text: str) -> tuple[str, str | None]:
    """"...Illegal or MAY 2014" -> ("...Illegal or", "MAY 2014")."""
    match = re.search(rf"\s+\(?({_MONTH}\s+\d{{4}})\)?$", text, re.IGNORECASE)
    if match and match.start() > 0:
        return text[: match.start()].strip(), match.group(1)
    return text, None


def _is_column_header(row: list[list[Word]]) -> bool:
    key = compact(" ".join(_text(p) for p in row))
    return "title" in key and ("date" in key or "number" in key) and not re.search(r"\d", key)


def _reference_rows(
    page: PageLines, top: float, bottom: float, context: _Context
) -> list[ClauseRecord]:
    """Clause list rows between y=top and y=bottom on one page.

    Two layouts: the title starts on the number's row and wraps below it
    (lines under a row belong to it), or the number is vertically centred
    on a two-line title (FA30: neighbouring lines split by distance)."""
    words = [w for w in page.words if top <= (w.y0 + w.y1) / 2 < bottom]
    rows = [row for row in _row_groups(words) if not _is_column_header(row)]
    anchor_rows: list[int] = []
    for i, row in enumerate(rows):
        if _CLAUSE_START.match(_text(row[0])):
            anchor_rows.append(i)
    if not anchor_rows:
        return []
    number_x = min(rows[i][0][0].x0 for i in anchor_rows)
    anchor_rows = [i for i in anchor_rows if rows[i][0][0].x0 <= number_x + 25]
    if not anchor_rows:
        return []

    def centre(i: int) -> float:
        return (rows[i][0][0].y0 + rows[i][0][0].y1) / 2

    def has_title(i: int) -> bool:
        number_text = _text(rows[i][0])
        rest = number_text[_CLAUSE_START.match(number_text).end():].strip()
        others = [_text(p) for p in rows[i][1:]]
        return bool(rest) or any(
            not _DATE_ONLY.match(t) and not _COLUMN_VALUE.fullmatch(t.strip()) for t in others
        )

    pitch = 12.0
    owned: dict[int, list[int]] = {i: [i] for i in anchor_rows}
    orphans_before = [i for i in range(anchor_rows[0]) if centre(anchor_rows[0]) - centre(i) <= 1.4 * pitch]
    if orphans_before and not has_title(anchor_rows[0]):
        owned[anchor_rows[0]] = orphans_before + owned[anchor_rows[0]]
    for n, a in enumerate(anchor_rows):
        b = anchor_rows[n + 1] if n + 1 < len(anchor_rows) else None
        between = list(range(a + 1, b if b is not None else len(rows)))
        if b is None:
            between = [i for i in between if centre(i) - centre(a) <= 2.5 * pitch]
            owned[a].extend(between)
            continue
        if has_title(b):
            owned[a].extend(between)
            continue
        for i in between:
            target = a if centre(i) - centre(a) <= centre(b) - centre(i) else b
            owned[target].append(i)

    records: list[ClauseRecord] = []
    for a in anchor_rows:
        number_phrase = rows[a][0]
        number_text = _text(number_phrase)
        number_match = _CLAUSE_START.match(number_text)
        number = number_match.group("number")
        remainder = number_text[number_match.end():].strip()
        dev = number_match.group("dev")
        pieces: list[str] = []
        date = None
        extra: list[str] = []
        phrases = [(i, p) for i in sorted(owned[a]) for p in rows[i] if p is not number_phrase]
        if remainder:
            phrases.insert(0, (a, None))
        for i, phrase in sorted(phrases, key=lambda item: (centre(item[0]), item[1][0].x0 if item[1] else 0)):
            text = remainder if phrase is None else _text(phrase)
            if _DATE_ONLY.match(text):
                if date is None:
                    date = text.strip("()")
                elif extra:
                    extra[-1] = f"{extra[-1]} ({text.strip('()')})"  # the deviation's own date
                continue
            # Alternate / deviation column values, wherever the row puts
            # them ("Deviation 2022-O0001 Oct 2021" merges with its date).
            column_value = _COLUMN_VALUE.fullmatch(text.strip())
            if phrase is not None and column_value:
                extra.append(column_value.group(1))
                if column_value.group(4) and date is None:
                    date = column_value.group(4)
                continue
            head, trailing = _split_trailing_date(text)
            if trailing and date is None:
                date, text = trailing, head
            # "... Concerns Deviation 2023-O0002": the deviation column ran
            # into the title.
            tail = re.search(r"\s+(Deviation\s+[A-Z0-9]+-[A-Z0-9]+)$", text)
            if tail:
                extra.append(tail.group(1))
                text = text[: tail.start()]
            if text:
                pieces.append(text)
        title, inline_date, alternate = _clean_title(" ".join(pieces))
        deviation = " ".join(_DEVIATION.findall(title))
        title = _DEVIATION.sub("", title).strip(" .")
        title = re.sub(r"\s{2,}", " ", title)
        alt_parts = [part for part in (alternate, dev and dev.strip(), deviation or None, *extra) if part]
        if not title:
            continue
        used = [w for i in owned[a] for p in rows[i] for w in p]
        records.append(
            ClauseRecord(
                clause_number=number,
                title=title,
                date=(date or inline_date),
                alternate=_dedupe_parts(alt_parts),
                regulation=_regulation(number, context.hint),
                incorporation_type=context.incorporation,
                page=page.page_number,
                bbox=(min(w.x0 for w in used), min(w.y0 for w in used), max(w.x1 for w in used), max(w.y1 for w in used)),
                # Source phrases in column order: number, title lines, date
                # (the date sits between wrapped title lines on the page).
                evidence=" ".join(part for part in [number_text, *pieces, date or "", *extra] if part),
                source_heading=context.heading,
            )
        )
    return records


def _full_text_heading(lines: list[LogicalLine], index: int) -> tuple[str, str, str | None, str | None, int] | None:
    """(number, title, date, alternate, lines consumed) when lines[index]
    starts a full-text clause: number at the start, a title, and its date
    on that line or within the next two lines."""
    line = lines[index]
    stripped = line.text.strip()
    prefix = _OUTLINE_CLAUSE.match(stripped)
    if prefix:
        stripped = stripped[prefix.end():]
    match = _CLAUSE_START.match(stripped)
    if not match:
        return None
    rest = stripped[match.end():].strip()
    if not rest or not (rest[0].isupper() or rest[0] in "\"'(" and rest[1:2].isupper()):
        return None
    consumed = 1
    title_text = rest
    dated = re.compile(rf"{_MONTH}\s+\d{{4}}\)?\s*\.?(\s*\((DEVIATION|Deviation)[^)]*\)?)*\s*$", re.IGNORECASE)
    if not dated.search(title_text):
        for extra in lines[index + 1:index + 3]:
            title_text = f"{title_text} {extra.text.strip()}"
            consumed += 1
            if dated.search(extra.text.strip()):
                break
        else:
            return None
    deviation_tail = re.search(r"(\s*\((DEVIATION|Deviation)[^)]*\)?)+\s*$", title_text)
    tail = deviation_tail.group(0).strip() if deviation_tail else ""
    if deviation_tail:
        title_text = title_text[: deviation_tail.start()]
    title_text = re.sub(rf"\s+\(?({_MONTH}\s+\d{{4}})\)?\s*\.?\s*$", r" (\1)", title_text, flags=re.IGNORECASE)
    title_text = f"{title_text} {tail}".strip()
    title, date, alternate = _clean_title(title_text)
    if not title or len(title) > 220:
        return None
    if len(title.split()) > 24:
        return None  # a sentence that happens to start with a clause number
    deviation = " ".join(_DEVIATION.findall(title)) or (match.group("dev") or "").strip()
    title = _DEVIATION.sub("", title).strip(" .")
    alternate = _dedupe_parts([*(alternate or "").split("; "), deviation or None])
    return match.group("number"), title, date, alternate, consumed


def _visual_rows(page: PageLines) -> list[LogicalLine]:
    rows: list[list[LogicalLine]] = []
    for line in sorted(page.lines, key=lambda line: (line.y0, line.x0)):
        if rows and abs(line.y0 - rows[-1][0].y0) <= 2.5:
            rows[-1].append(line)
        else:
            rows.append([line])
    merged: list[LogicalLine] = []
    for row in rows:
        row.sort(key=lambda line: line.x0)
        first = row[0]
        merged.append(
            replace(
                first,
                text="  ".join(line.text.strip() for line in row),
                x1=max(line.x1 for line in row),
                y1=max(line.y1 for line in row),
            )
        )
    return merged


def read_clauses(pages: list[PageLines]) -> list[ClauseRecord]:
    records: list[ClauseRecord] = []
    context: _Context | None = None
    open_clause: ClauseRecord | None = None
    body: list[LogicalLine] = []

    def close() -> None:
        nonlocal open_clause, body
        if open_clause is not None:
            open_clause.text = join_paragraphs(body).strip() or None
            records.append(open_clause)
        open_clause, body = None, []

    for page in pages:
        lines = _visual_rows(page)
        if sum(1 for line in lines if re.search(r"\.{5,}", line.text)) >= 5:
            continue  # a table-of-contents page: entries are not clauses
        # Merge a heading wrapped over two lines ("... Clauses Incorporated
        # By" / "Reference").
        index = 0
        segment_top: float | None = 0.0 if context and context.incorporation == BY_REFERENCE else None
        while index < len(lines):
            line = lines[index]
            text = line.text.strip()
            if re.search(r"\.{5,}", text):
                index += 1  # a table-of-contents entry
                continue
            joined = f"{text} {lines[index + 1].text.strip()}" if index + 1 < len(lines) else text
            heading = incorporation_heading(text) or (
                incorporation_heading(joined) if re.search(r"\b(by|in)$", text, re.IGNORECASE) else None
            )
            outline_clause = bool(_OUTLINE.match(text)) and heading is None and _full_text_heading(lines, index) is not None
            ends_context = bool(_SECTION_HEADING.match(text)) or (
                bool(_OUTLINE.match(text)) and heading is None and not outline_clause
            )
            if heading or ends_context:
                if segment_top is not None and context and context.incorporation == BY_REFERENCE:
                    records.extend(_reference_rows(page, segment_top, line.y0, context))
                close()
                segment_top = None
                context = heading
                if context and context.incorporation == BY_REFERENCE:
                    segment_top = line.y1 + (lines[index + 1].y1 - line.y1 if heading and joined != text and heading.heading == joined else 0)
                index += 2 if heading and heading.heading == joined and joined != text else 1
                continue
            if outline_clause and (context is None or context.incorporation == BY_REFERENCE):
                if segment_top is not None and context:
                    records.extend(_reference_rows(page, segment_top, line.y0, context))
                segment_top = None
                hint = next((name for token, name in _REGULATION_HINTS if token in compact(text)[:12]), None)
                context = _Context(IN_FULL_TEXT, hint, text)
            if context and context.incorporation == IN_FULL_TEXT:
                hit = _full_text_heading(lines, index)
                if hit and open_clause is not None and hit[0] == open_clause.clause_number:
                    hit = None
                if hit:
                    close()
                    number, title, date, alternate, consumed = hit
                    used = lines[index:index + consumed]
                    open_clause = ClauseRecord(
                        clause_number=number,
                        title=title,
                        date=date,
                        alternate=alternate,
                        regulation=_regulation(number, context.hint),
                        incorporation_type=IN_FULL_TEXT,
                        page=page.page_number,
                        bbox=(min(l.x0 for l in used), min(l.y0 for l in used), max(l.x1 for l in used), max(l.y1 for l in used)),
                        evidence=" ".join(l.text.strip() for l in used),
                        source_heading=context.heading,
                    )
                    index += consumed
                    continue
                if open_clause is not None:
                    body.append(line)
                    open_clause.end_page = page.page_number
            index += 1
        if segment_top is not None and context and context.incorporation == BY_REFERENCE:
            records.extend(_reference_rows(page, segment_top, page.height + 1, context))
    close()
    return records
