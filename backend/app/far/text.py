"""FAR Part PDF (page text) → the same records the HTML parser produces.

A FAR Part printed from acquisition.gov opens with its table of contents
("Part 37 - Service Contracting", then every Subpart / section heading),
ends it with "Parent topic: Federal Acquisition Regulation", and then
repeats each heading above its own text. The table of contents fixes the
record order: a body paragraph is a heading only when it is the next
heading the contents list (so "37.104 and the guidelines …" inside a
paragraph is never a record), and a heading the page break split
("Subpart 37.3 - Dismantling, Demolition, or Removal of" / "Improvements")
is joined back to the title the contents give. Without contents, numbered
headings of the Part in ascending order are used.

Paragraphs are the page text's blank-line separated blocks; a paragraph's
wrapped lines are joined with single spaces. Words are never rewritten.
Deterministic — no OCR, no AI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.far.dom import (
    _ALTERNATE,
    _END_MARKER,
    _HEADING_DATE,
    _INSERT_KIND,
    _PRESCRIPTION,
    _PRESCRIPTION_REFERENCE,
    _RESERVED,
    _RESERVED_ALTERNATE,
    FarAlternate,
    FarExtraction,
    FarRecognition,
    FarSourceRecord,
    _references,
    clean,
    clear_parent_no_body,
    month_year,
    score_far_structure,
)

_DASH = r"\s*[-‐-―]\s*"
_PART_LINE = re.compile(r"^Part\s+(?P<part>\d{1,2})" + _DASH + r"(?P<title>\S.*)$")
_SUBPART_LINE = re.compile(r"^Subpart\s+(?P<number>\d{1,2}\.\d+)" + _DASH + r"(?P<title>\S.*)$")
_SECTION_LINE = re.compile(r"^(?P<number>\d{1,2}\.\d{3,4}(?:-\d+)?)\s+(?P<title>\S.*)$")
_PARENT_TOPIC = re.compile(r"^Parent topic:", re.I)
_MAX_HEADING = 200


@dataclass
class Paragraph:
    page: int
    text: str


@dataclass
class _Heading:
    index: int  # paragraph index of the heading's first paragraph
    end: int  # paragraph index after the heading (wrapped titles span several)
    number: str  # "37.101" or "Subpart 37.1"
    title: str
    heading_text: str
    page: int


def paragraphs(pages: list[tuple[int, str]]) -> list[Paragraph]:
    out: list[Paragraph] = []
    for page, text in pages:
        for block in re.split(r"\n\s*\n", (text or "").replace("\r", "")):
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if not lines:
                continue
            joined = lines[0]
            for line in lines[1:]:
                # "fixed-" / "price": a word broken at the line end.
                if joined.endswith("-") and not joined.endswith(" -") and line[:1].islower():
                    joined += line
                else:
                    joined += " " + line
            out.append(Paragraph(page, clean(joined)))
    return out


def _heading_of(text: str, part: str | None) -> tuple[str, str] | None:
    """(number, title) when the paragraph reads as a heading of the Part."""

    if len(text) > _MAX_HEADING:
        return None
    match = _SUBPART_LINE.match(text)
    if match:
        number = match.group("number")
        if part is None or number.split(".")[0] == part:
            return f"Subpart {number}", match.group("title").strip()
        return None
    match = _SECTION_LINE.match(text)
    if match:
        number = match.group("number")
        if part is None or number.split(".")[0] == part:
            return number, match.group("title").strip()
    return None


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _sort_key(number: str) -> tuple:
    digits = [int(n) for n in re.findall(r"\d+", number.replace("Subpart ", ""))]
    major, minor = digits[0], digits[1] if len(digits) > 1 else 0
    if number.startswith("Subpart"):
        # Subpart 37.1 sorts before 37.100.
        return (major, minor * 100 - 1, -1)
    return (major, minor, digits[2] if len(digits) > 2 else 0)


def _toc(paras: list[Paragraph], part: str | None) -> tuple[list[tuple[str, str]], int]:
    """(contents entries, index of the first body paragraph). The contents
    are the leading run of headings; the body starts where a heading
    repeats. No repeat → no contents."""

    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index, para in enumerate(paras):
        if _PART_LINE.match(para.text) and not entries:
            continue
        if _PARENT_TOPIC.match(para.text):
            continue
        heading = _heading_of(para.text, part)
        if heading is None:
            break
        if heading[0] in seen:
            return entries, index
        seen.add(heading[0])
        entries.append(heading)
    return [], 0


def _find_headings(paras: list[Paragraph], part: str | None) -> tuple[list[_Heading], int]:
    entries, start = _toc(paras, part)
    headings: list[_Heading] = []
    if entries:
        position = 0
        index = start
        while index < len(paras) and position < len(entries):
            heading = _heading_of(paras[index].text, part)
            match_at = None
            if heading:
                # The next contents entry, tolerating a few the body skipped.
                for k in range(position, min(position + 4, len(entries))):
                    if entries[k][0] == heading[0]:
                        match_at = k
                        break
            if match_at is None:
                index += 1
                continue
            number, toc_title = entries[match_at]
            title, end = heading[1], index + 1
            # A page break split the heading: join until it is the
            # contents' title.
            while _norm(title) != _norm(toc_title) and _norm(toc_title).startswith(_norm(title)) and end < len(paras):
                candidate = f"{title} {paras[end].text}"
                if not _norm(toc_title).startswith(_norm(candidate)):
                    break
                title, end = candidate, end + 1
            text = paras[index].text if end == index + 1 else f"{paras[index].text.split(heading[1])[0]}{title}"
            headings.append(_Heading(index, end, number, title, clean(text), paras[index].page))
            position = match_at + 1
            index = end
        return headings, start
    last: tuple | None = None
    for index, para in enumerate(paras):
        heading = _heading_of(para.text, part)
        if heading is None:
            continue
        number, title = heading
        if not number.startswith("Subpart") and not title.rstrip().endswith((".", "]")):
            continue
        key = _sort_key(number)
        if last is not None and key <= last:
            continue
        last = key
        headings.append(_Heading(index, index + 1, number, title, para.text, para.page))
    return headings, 0


def _part_of(paras: list[Paragraph]) -> tuple[str | None, str | None]:
    for para in paras[:5]:
        match = _PART_LINE.match(para.text)
        if match:
            return match.group("part"), para.text
    return None, None


def _strip_title(title: str) -> str:
    title = title.strip()
    return title[:-1].rstrip() if title.endswith(".") and not title.endswith("...") else title


def _nonspace(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _record(
    sequence: int,
    heading: _Heading,
    body: list[Paragraph],
    trail: list[str],
    subpart: tuple[str, str] | None,
) -> FarSourceRecord:
    number = heading.number
    title = _strip_title(heading.title)
    if number.startswith("Subpart"):
        kind = "subpart"
    elif _RESERVED.match(title):
        kind = "reserved"
    else:
        kind = "section"
    pages = [heading.page, *(p.page for p in body)]
    location = f"page {heading.page}" + (f"-{max(pages)}" if max(pages) != heading.page else "")

    basic: list[Paragraph] = []
    groups: list[list[Paragraph]] = []
    for para in body:
        if _ALTERNATE.match(para.text) or _RESERVED_ALTERNATE.match(para.text):
            groups.append([para])
        elif groups:
            groups[-1].append(para)
        else:
            basic.append(para)
    grouped = "\n".join(p.text for p in body)
    record = FarSourceRecord(
        sequence=sequence,
        far_number=number,
        kind=kind,
        heading_text=heading.heading_text,
        title=title,
        element_id=None,
        dom_path=location,
        heading_dom_path=f"page {heading.page}",
        section_path=[*trail, heading.heading_text],
        subpart=number if kind == "subpart" else (subpart[0] if subpart else None),
        subpart_title=title if kind == "subpart" else (subpart[1] if subpart else None),
        grouped_text=grouped,
        basic_text="\n".join(p.text for p in basic),
        source_char_count=sum(_nonspace(p.text) for p in body),
        rendered_char_count=_nonspace(grouped),
    )
    record.page = heading.page
    record.end_page = max(pages)
    if kind == "subpart":
        return record

    for para in basic[:3]:
        date = _HEADING_DATE.search(para.text)
        if date and len(para.text) <= _MAX_HEADING:
            record.official_heading = para.text
            record.official_heading_dom_path = f"page {para.page}"
            record.revision_date = month_year(date.group("month"), date.group("year"))
            break
    if basic and _PRESCRIPTION.match(basic[0].text):
        record.prescription = basic[0].text
        record.prescription_dom_path = f"page {basic[0].page}"
        ref = _PRESCRIPTION_REFERENCE.match(basic[0].text)
        record.prescription_reference = ref.group("ref") if ref else None
        kind_match = _INSERT_KIND.search(basic[0].text)
        if kind_match:
            record.clause_type = kind_match.group("kind").capitalize()
            record.clause_type_evidence = basic[0].text
    if record.clause_type is None:
        for para in basic:
            end = _END_MARKER.match(para.text)
            if end:
                record.clause_type = end.group("kind").capitalize()
                record.clause_type_evidence = para.text
                break
    for group in groups:
        first = group[0].text
        match = _ALTERNATE.match(first) or _RESERVED_ALTERNATE.match(first)
        reserved = match.re is _RESERVED_ALTERNATE
        instruction = "" if reserved else first[match.end():].strip()
        ref = _PRESCRIPTION_REFERENCE.match(instruction)
        text = "\n".join(p.text for p in group)
        record.alternates.append(
            FarAlternate(
                code=f"Alternate {match.group('roman')}",
                roman=match.group("roman"),
                date=None if reserved else month_year(match.group("month"), match.group("year")),
                reserved=reserved,
                heading=first if reserved else first[: match.end()].strip().rstrip(".").strip(),
                instruction=instruction,
                prescription_reference=ref.group("ref") if ref else None,
                text=text,
                element_id=None,
                dom_path=f"page {group[0].page}",
                embedded_references=_references(text, number),
            )
        )
    record.embedded_references = _references(record.grouped_text, number)
    record.basic_embedded_references = _references(record.basic_text, number)
    if kind == "section" and not record.grouped_text:
        record.issues.append("Section heading has no body text.")
    return record


def extract_far_text(pages: list[tuple[int, str]]) -> FarExtraction:
    paras = paragraphs(pages)
    part, part_heading = _part_of(paras)
    headings, _start = _find_headings(paras, part)
    records: list[FarSourceRecord] = []
    trail_root = [part_heading] if part_heading else []
    subpart: tuple[str, str] | None = None
    subpart_heading: str | None = None
    for position, heading in enumerate(headings):
        stop = headings[position + 1].index if position + 1 < len(headings) else len(paras)
        body = [p for p in paras[heading.end : stop] if not _PARENT_TOPIC.match(p.text)]
        if heading.number.startswith("Subpart"):
            subpart = (heading.number, _strip_title(heading.title))
            subpart_heading = heading.heading_text
            trail = trail_root
        else:
            trail = [*trail_root, subpart_heading] if subpart_heading else trail_root
        records.append(_record(len(records) + 1, heading, body, trail, subpart if not heading.number.startswith("Subpart") else None))
    clear_parent_no_body(records)
    warnings = [] if headings else ["No FAR section headings found in the page text."]
    return FarExtraction(
        part_heading=part_heading,
        records=records,
        article_count=len(records) + (1 if part_heading else 0),
        warnings=warnings,
    )


def recognize_far_text(pages: list[tuple[int, str]]) -> FarRecognition:
    """The same structural evidence as the HTML recognizer, read from page
    text: a "Part N - Title" opening, Subpart N.x headings and numbered
    section headings of that Part on their own lines."""

    paras = paragraphs(pages)
    part, _heading = _part_of(paras)
    subparts: set[str] = set()
    numbered: set[str] = set()
    prescribed = 0
    parent_topic = False
    for para in paras:
        if _PARENT_TOPIC.match(para.text) and "Federal Acquisition Regulation" in para.text:
            parent_topic = True
        if _PRESCRIPTION.match(para.text):
            prescribed += 1
        heading = _heading_of(para.text, part)
        if heading is None:
            continue
        if heading[0].startswith("Subpart"):
            subparts.add(heading[0])
        elif heading[1].rstrip().endswith((".", "]")):
            numbered.add(heading[0])
    return score_far_structure(part, len(subparts), len(numbered), prescribed, parent_topic)
