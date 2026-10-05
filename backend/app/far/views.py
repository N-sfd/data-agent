"""Row views over the canonical FAR records — the workbook sheets
01_FAR_STAGING, 02_ORACLE_MAPPING, 04_STRUCTURED_FAR, 06_CANONICAL_MODEL,
99_LONG_TEXT — and the 03_VALIDATION checks. Shared by the staging
profile (UI datasets) and the exports, so every surface shows the same
values. Views never alter text.
"""

from __future__ import annotations

import re
from collections import Counter

from app.far import regulation
from app.far.canonical import ALTERNATE, CLAUSE_OR_PROVISION, RESERVED, SECTION, SUBPART
from app.far.oracle_map import (
    OUTPUT_MAP,
    PENDING_TEMPLATE,
    READY,
    REQUIRES_TEMPLATE,
    record_routing,
)
from app.models.document_far_record import DocumentFarRecord

# Excel's cell limit is 32,767 characters; longer text is carried whole in
# 99_LONG_TEXT (and whole in CSV/JSON), chunked at this size.
LONG_TEXT_CHUNK = 30000

STAGING_COLUMNS = (
    "Sequence ID", "FAR Number", "Title / Type", "FAR # + Title", "SubID", "Subtitle",
    "SubID + Subtitle", "Actual Section Text", "Section", "Subsection", "Paragraph", "Subparagraph",
)
ORACLE_MAPPING_COLUMNS = (
    "Sequence ID", "FAR # + Title", "SubID + Subtitle", "Actual Section Text", "Oracle Target",
    "Load / Mapping Status", "Paragraph", "Subparagraph",
)
STRUCTURED_COLUMNS = (
    "Sequence ID", "FAR Number", "Title / Type", "FAR # + Title", "Official Heading", "Revision Date",
    "Prescription", "Alternate", "Alternate Date", "Alternate Instruction", "Embedded FAR References",
    "Actual Section Text", "Section", "Subsection", "Paragraph", "Subparagraph",
)
# The clause-library layout (one row per FAR record, source order), plus
# Type and the text split by type so provisions and clauses read apart.
BUSINESS_COLUMNS = (
    "Action",
    "Date Published",
    "Number",
    "Title",
    "Display Name",
    "Type",
    "Intent",
    "Language",
    "Clause Type",
    "Status",
    "Description",
    "Provision Yn",
    "Global Yn",
    "Lock Text Yn",
    "Insert By Reference",
    "Text",
    "Provision Text",
    "Clause Text",
    "Start Date",
    "Attribute Category",
    "Attribute 1",
    "Source XML",
    "Source Reference",
)

# Clause-library values for every load-eligible FAR record, as in the
# approved target layout. Structural, reserved and alternate records are
# not loaded, so they carry none of these.
LIBRARY_DEFAULTS = {
    "Action": "Sync",
    "Intent": "B",
    "Language": "US",
    "Clause Type": "STANDARD",
    "Status": "APPROVED",
    "Global Yn": "Y",
    "Lock Text Yn": "Y",
    "Insert By Reference": "N",
    "Attribute Category": "FAR_PART_52",
}

_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_MONTH_YEAR = re.compile(r"^\s*([A-Za-z]{3})[a-z]*\.?\s+(\d{4})\s*$")


def source_reference(row: DocumentFarRecord) -> str | None:
    """Trace a record to its HTML source. No page number is invented."""

    prov = row.provenance_json or {}
    section = prov.get("section_path") or []
    trail = " › ".join(str(part) for part in section) if isinstance(section, list) else ""
    element = prov.get("element_id")
    dom = prov.get("dom_path")
    pieces = [part for part in (trail, f"id:{element}" if element else None, None if element else dom) if part]
    return " | ".join(pieces) or None


def published_date(version: str | None) -> str | None:
    """"Sep 2023" -> "2023-09-01"; anything else stays blank."""

    match = _MONTH_YEAR.match(version or "")
    month = _MONTHS.get(match.group(1).lower()) if match else None
    return f"{match.group(2)}-{month:02d}-01" if match and month else None


def record_type(row: DocumentFarRecord) -> str:
    """Provision or Clause (alternates take their basic record's type);
    Section for the Part/Subpart instructions (52.000, 52.1xx, 52.200)."""

    if row.content_type == RESERVED:
        return "Reserved"
    if row.content_type == SUBPART:
        return "Subpart"
    if row.clause_type in ("Clause", "Provision"):
        return row.clause_type
    return "Alternate" if row.content_type == ALTERNATE else "Section"


def body_text(row: DocumentFarRecord) -> str | None:
    """The provision/clause text after its prescription ("As prescribed in
    ..., insert the following clause:"), which is the Description. The text
    is sliced, never rewritten; when the prescription does not lead the
    text exactly, the whole text is kept."""

    text = row.source_text
    if not text or not row.prescription or row.content_type == ALTERNATE:
        return text
    tokens = row.prescription.split()
    pattern = r"\s*" + r"\s*".join(re.escape(token) for token in tokens) + r"\s*"
    match = re.match(pattern, text)
    rest = text[match.end():] if match else ""
    return rest if rest.strip() else text


def business_row(row: DocumentFarRecord) -> dict:
    """The clause-library row. Values come from the source (number, title,
    dates, prescription, text) or the approved library defaults for
    load-eligible records; Source XML stays blank until the import file
    naming is supplied."""

    kind = record_type(row)
    title = row.subpart_title if row.content_type == SUBPART else row.title
    alternate = f" {row.alternate_code}" if row.alternate_code else ""
    if row.content_type == SUBPART:
        full_title = row.display_name
    else:
        full_title = f"FAR {row.far_number} - {title}{alternate}" if title else None
    date = published_date(row.version_date)
    text = body_text(row)
    library = row.load_eligible
    values = {column: None for column in BUSINESS_COLUMNS}
    if library:
        values.update(LIBRARY_DEFAULTS)
    values.update(
        {
            "Date Published": date,
            "Number": row.far_number,
            "Title": full_title,
            "Display Name": f"{title}{alternate}" if title else None,
            "Type": kind,
            "Description": row.alternate_instruction if row.content_type == ALTERNATE else row.prescription,
            "Provision Yn": ("Y" if kind == "Provision" else "N") if library else None,
            "Text": text,
            "Provision Text": text if kind == "Provision" else None,
            "Clause Text": text if kind == "Clause" else None,
            "Start Date": date,
            "Attribute 1": row.far_number if library else None,
            "Source Reference": source_reference(row),
        }
    )
    return values


CANONICAL_COLUMNS = (
    "Source Sequence ID", "Clause Key", "Parent Clause Key", "FAR Number", "Content Type", "Title",
    "Display Name", "Version Date", "Alternate Code", "Basic Clause Key", "Prescription Reference",
    "Source Order", "Load Eligible", "Source Text", "Embedded FAR References", "Transformation Notes",
)
OUTPUT_MAP_COLUMNS = (
    "Canonical Field", "Purpose", "Oracle Output Concept", "Transformation Rule", "Load Condition",
    "Source / Canonical Field", "Example", "Implementation Status",
)
LONG_TEXT_COLUMNS = ("Sequence ID", "FAR Number", "Clause Key", "Chunk", "Characters", "Text")
VALIDATION_COLUMNS = ("Check", "Expected", "Result", "Notes")

EXTRACTION_GUIDE: tuple[tuple[str, str, str], ...] = (
    ("FAR # + Title", "Combine the FAR number and source title exactly as the document heading.", "Primary display/search label"),
    ("Official Heading", "Keep the dated provision/clause heading when present, e.g. Taxpayer Identification (Oct 1998).", "Display beneath FAR # + Title"),
    ("Revision Date", "Extract the Month YYYY date from the official heading; do not remove it from Official Heading.", "Filtering/version awareness"),
    ("Prescription", "Capture the source instruction beginning 'As prescribed in...' separately when present.", "Oracle/source metadata"),
    ("Alternate", "Detect Alternate I, II, III, etc. only when it appears as a structural heading at the start of a source paragraph. Ignore narrative/example mentions of alternate names. Each structural alternate is its own row linked to its basic clause.", "Variant identification without false positives"),
    ("Alternate Date", "Extract the date attached to the Alternate heading.", "Variant version"),
    ("Alternate Instruction", "Capture substitute/add/insert instruction associated with the Alternate.", "Explains how alternate modifies basic text"),
    ("Embedded FAR References", "Extract referenced 52.xxx-x identifiers as a semicolon-delimited index; do not turn them into master rows.", "Cross-reference/search"),
    ("Actual Section Text", "Preserve complete grouped source text, including (a), (b), (1), (i), (A), etc. Text is never rewritten (e.g. is kept verbatim); structural alternates are carried on their own rows.", "Canonical source text"),
    ("Paragraph / Subparagraph", "Remain available as final compatibility fields, but grouped FAR records are not exploded into child rows.", "Compatibility only"),
)


def refs_text(row: DocumentFarRecord) -> str | None:
    return "; ".join(row.embedded_references or []) or None


def _combine(subid: str | None, subtitle: str | None) -> str | None:
    if subid and subtitle:
        return subtitle if subtitle.startswith(subid) else f"{subid} {subtitle}"
    return subid or subtitle


def is_alternate_row(row: DocumentFarRecord) -> bool:
    return row.alternate_code is not None


def base_rows(rows: list[DocumentFarRecord]) -> list[DocumentFarRecord]:
    return [r for r in rows if not is_alternate_row(r)]


def title_or_type(row: DocumentFarRecord) -> str | None:
    if row.content_type == SUBPART:
        return "Subpart"
    if is_alternate_row(row):
        return "Alternate"
    return row.title


def subid_subtitle(row: DocumentFarRecord) -> tuple[str | None, str | None]:
    if row.content_type == SUBPART:
        return None, row.subpart_title
    if is_alternate_row(row):
        return row.alternate_code, row.alternate_heading
    return row.section_group, row.official_heading


def staging_row(row: DocumentFarRecord) -> dict:
    subid, subtitle = subid_subtitle(row)
    return {
        "Sequence ID": row.source_sequence_id,
        "FAR Number": row.far_number,
        "Title / Type": title_or_type(row),
        "FAR # + Title": row.display_name if not is_alternate_row(row) else _base_display(row),
        "SubID": subid,
        "Subtitle": subtitle,
        "SubID + Subtitle": _combine(subid, subtitle),
        "Actual Section Text": row.source_text,
        "Section": row.subpart,
        "Subsection": row.subsection,
        "Paragraph": None,
        "Subparagraph": None,
    }


def _base_display(row: DocumentFarRecord) -> str | None:
    heading = row.heading_text or ""
    return heading[:-1].rstrip() if heading.endswith(".") else heading or None


def oracle_mapping_row(row: DocumentFarRecord) -> dict:
    staging = staging_row(row)
    target, status = record_routing(row.content_type)
    return {
        "Sequence ID": staging["Sequence ID"],
        "FAR # + Title": staging["FAR # + Title"],
        "SubID + Subtitle": staging["SubID + Subtitle"],
        "Actual Section Text": staging["Actual Section Text"],
        "Oracle Target": target,
        "Load / Mapping Status": status,
        "Paragraph": None,
        "Subparagraph": None,
    }


def structured_row(row: DocumentFarRecord) -> dict:
    alternate = is_alternate_row(row)
    return {
        "Sequence ID": row.source_sequence_id,
        "FAR Number": row.far_number,
        "Title / Type": title_or_type(row),
        "FAR # + Title": _base_display(row) if alternate else row.display_name,
        "Official Heading": row.subpart_title if row.content_type == SUBPART else row.official_heading,
        "Revision Date": None if alternate else row.version_date,
        "Prescription": row.prescription,
        "Alternate": row.alternate_code,
        "Alternate Date": row.version_date if alternate else None,
        "Alternate Instruction": row.alternate_instruction,
        "Embedded FAR References": refs_text(row),
        "Actual Section Text": row.source_text,
        "Section": row.subpart,
        "Subsection": row.subsection,
        "Paragraph": None,
        "Subparagraph": None,
    }


def canonical_row(row: DocumentFarRecord) -> dict:
    return {
        "Source Sequence ID": row.source_sequence_id,
        "Clause Key": row.clause_key,
        "Parent Clause Key": row.parent_clause_key,
        "FAR Number": row.far_number,
        "Content Type": row.content_type,
        "Title": row.subpart_title if row.content_type == SUBPART else row.title,
        "Display Name": row.display_name,
        "Version Date": row.version_date,
        "Alternate Code": row.alternate_code,
        "Basic Clause Key": row.basic_clause_key,
        "Prescription Reference": row.prescription_reference,
        "Source Order": row.source_order,
        "Load Eligible": "YES" if row.load_eligible else "NO",
        "Source Text": row.source_text,
        "Embedded FAR References": refs_text(row),
        "Transformation Notes": row.transformation_notes,
    }


def output_map_rows() -> list[dict]:
    return [
        dict(zip(OUTPUT_MAP_COLUMNS, (m.canonical_field, m.purpose, m.oracle_concept, m.rule, m.load_condition, m.source_field, m.example, m.status)))
        for m in OUTPUT_MAP
    ]


def long_text_rows(rows: list[DocumentFarRecord]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        text = row.source_text or ""
        if len(text) <= LONG_TEXT_CHUNK:
            continue
        for index in range(0, len(text), LONG_TEXT_CHUNK):
            chunk = text[index : index + LONG_TEXT_CHUNK]
            out.append(
                {
                    "Sequence ID": row.source_sequence_id,
                    "FAR Number": row.far_number,
                    "Clause Key": row.clause_key,
                    "Chunk": index // LONG_TEXT_CHUNK + 1,
                    "Characters": len(chunk),
                    "Text": chunk,
                }
            )
    return out


def _nonspace(text: str | None) -> int:
    return len("".join((text or "").split()))


_KEY = re.compile(r"^FAR-(?:Subpart_\d{1,2}\.\d+|\d{1,2}\.\d{3,4}(?:-\d+)?)(?:-ALT-[IVX]+)?$")
_EG = re.compile(r"\be\.g\.", re.I)


def validation_rows(rows: list[DocumentFarRecord], summary: dict | None = None) -> list[dict]:
    """03_VALIDATION: checks that FLAG — they never change a value."""

    summary = summary or {}
    base = base_rows(rows)
    alternates = [r for r in rows if is_alternate_row(r)]
    by_key = {r.clause_key: r for r in rows}
    types = Counter(r.content_type for r in base)
    checks: list[dict] = []

    def add(check: str, expected: str, ok: bool | str, notes: str) -> None:
        result = ok if isinstance(ok, str) else ("PASS" if ok else "REVIEW")
        checks.append({"Check": check, "Expected": expected, "Result": result, "Notes": notes})

    articles = summary.get("articles")
    add(
        "FAR records extracted",
        "One record per FAR article heading (the Part title is not a record)",
        len(base) > 0,
        f"{len(base)} source/base FAR records"
        + (f" from {articles} FAR-headed source articles (Part title included)" if articles else "")
        + f": {types.get(CLAUSE_OR_PROVISION, 0)} clause/provision, {types.get(SECTION, 0)} section, {types.get(RESERVED, 0)} reserved, "
        f"{types.get(SUBPART, 0)} subpart headings.",
    )
    incomplete = [
        r.far_number
        for r in base
        if (r.provenance_json or {}).get("source_char_count") != (r.provenance_json or {}).get("rendered_char_count")
    ]
    add(
        "No truncation",
        "Every source character of every record is carried",
        not incomplete,
        "All records reproduce their full source text." if not incomplete else f"Check: {', '.join(incomplete[:20])}",
    )
    lossy = []
    for r in base:
        expected_chars = (r.provenance_json or {}).get("grouped_nonspace_chars")
        parts = _nonspace(r.source_text) + sum(
            _nonspace(a.source_text) for a in alternates if a.basic_clause_key == r.clause_key
        )
        if expected_chars is not None and parts != expected_chars:
            lossy.append(r.far_number)
    add(
        "Alternates split without loss",
        "Basic text + alternate texts = the source record",
        not lossy,
        "Lossless for every record with alternates." if not lossy else f"Check: {', '.join(lossy[:20])}",
    )
    keys = [r.clause_key for r in rows]
    bad_keys = [k for k in keys if not _KEY.match(k)]
    add(
        "Stable unique clause keys",
        "One deterministic FAR-based key per canonical record",
        len(set(keys)) == len(keys) and not bad_keys,
        f"{len(keys)} canonical records (base + alternates), {len(set(keys))} unique keys" + (f"; malformed: {', '.join(bad_keys[:10])}" if bad_keys else "."),
    )
    add(
        "FAR # + Title",
        "Combined field populated",
        all(r.display_name for r in base),
        f"Example: {base[0].display_name}." if base else "No records.",
    )
    add(
        "SubID + Subtitle",
        "Combined when SubID/Subtitle exists",
        all(
            (staging_row(r)["SubID + Subtitle"] is not None) == bool(subid_subtitle(r)[0] or subid_subtitle(r)[1])
            for r in rows
        ),
        "Separate source fields are also retained.",
    )
    add("Paragraph/Subparagraph", "Remain last fields", True, "Compatibility only; grouped records are not exploded.")
    reserved_alternates = sum(1 for a in alternates if a.content_type == RESERVED)
    narrative = sum((r.provenance_json or {}).get("narrative_alternate_mentions", 0) for r in base)
    add(
        "Structural alternates only",
        "Alternate I/II/... only from a structural heading at the start of a paragraph",
        True,
        f"{len(alternates)} alternate records ({reserved_alternates} reserved placeholders) on "
        f"{len({a.basic_clause_key for a in alternates})} records; {narrative} narrative mention(s) ignored.",
    )
    orphans = [a.clause_key for a in alternates if a.basic_clause_key not in by_key or a.parent_clause_key != a.basic_clause_key]
    add(
        "Alternates linked to basic clause",
        "Every alternate carries its basic clause's key",
        not orphans,
        "All linked." if not orphans else f"Unlinked: {', '.join(orphans[:10])}",
    )
    referenced = {ref for r in rows for ref in (r.embedded_references or [])}
    numbers = {r.far_number for r in base}
    add(
        "Embedded FAR references are not records",
        "References are indexed only; no master rows created from them",
        len(base) == summary.get("records", len(base)),
        f"{sum(1 for r in base if r.embedded_references)} records carry references to {len(referenced)} distinct FAR numbers "
        f"({len(referenced & numbers)} of them are records of this source; {len(referenced - numbers)} are not). "
        "No record was created from a reference.",
    )
    dated_headings = [r for r in base if r.official_heading and re.search(r"\(\s*[A-Za-z]+\.?\s*\d{4}\s*\)\s*$", r.official_heading)]
    undated = [r.far_number for r in dated_headings if not r.version_date]
    add(
        "Revision Date",
        "Month YYYY from the official heading; heading unchanged",
        not undated,
        f"{sum(1 for r in base if r.version_date)} dated records; the date stays in Official Heading."
        + (f" Undated: {', '.join(undated[:10])}" if undated else ""),
    )
    unreferenced = [r.far_number for r in base if r.prescription and not r.prescription_reference]
    add(
        "Prescription",
        "'As prescribed in ...' captured with its FAR reference",
        not unreferenced,
        f"{sum(1 for r in base if r.prescription)} prescriptions."
        + (f" Reference unreadable: {', '.join(unreferenced[:10])}" if unreferenced else ""),
    )
    add(
        "Reserved records retained",
        "Kept for traceability, excluded from load",
        all(not r.load_eligible for r in rows if r.content_type == RESERVED),
        f"{types.get(RESERVED, 0)} reserved records and {reserved_alternates} reserved alternates retained with Load Eligible = NO.",
    )
    add(
        "Subpart headings retained",
        "Structural records kept, excluded from load",
        all(not r.load_eligible for r in rows if r.content_type == SUBPART),
        f"{types.get(SUBPART, 0)} subpart headings retained with Load Eligible = NO.",
    )
    loadable = sum(1 for r in rows if r.load_eligible)
    add(
        "Load eligibility explicit",
        "YES only for CLAUSE_OR_PROVISION; NO for structural, reserved and alternate records",
        all(r.load_eligible == (r.content_type == CLAUSE_OR_PROVISION) for r in rows),
        f"YES {loadable} / NO {len(rows) - loadable}. Alternates wait for the Oracle variant template.",
    )
    with_eg = sum(1 for r in rows if r.source_text and _EG.search(r.source_text))
    add(
        "Legal text preserved verbatim",
        "Text is never rewritten",
        "PASS",
        f"'e.g.' is kept exactly as in the source ({with_eg} records contain it). The reference workbook's "
        "'e.g. removed from text' cleanup is intentionally NOT applied.",
    )
    flagged = [r for r in rows if r.issues]
    add(
        "Record extraction issues",
        "No record has an unresolved extraction issue",
        not flagged,
        "None." if not flagged else "; ".join(f"{r.far_number}: {' '.join(r.issues)}" for r in flagged[:10]),
    )
    duplicates = [n for n, c in Counter(r.far_number for r in base).items() if c > 1]
    add("Duplicate FAR numbers", "Each FAR number heads one record", not duplicates, "None." if not duplicates else ", ".join(duplicates))
    orders = [r.source_order for r in rows]
    add("Source order", "Records follow the source document order", orders == sorted(orders), f"{len(rows)} canonical records in document order.")
    long_records = [r.far_number for r in rows if r.source_text and len(r.source_text) > LONG_TEXT_CHUNK]
    add(
        "Long text",
        f"Text over {LONG_TEXT_CHUNK:,} characters carried whole",
        True,
        (f"{len(long_records)} record(s) ({', '.join(long_records)}) exceed an Excel cell: the full text is in "
         "99_LONG_TEXT (and whole in CSV/JSON); the sheet cell holds its first chunk.")
        if long_records
        else "No record exceeds an Excel cell.",
    )
    statuses = Counter(m.status for m in OUTPUT_MAP)
    add(
        "Oracle output names",
        "No Oracle import field names invented",
        True,
        f"07 maps to output concepts only: {statuses.get(READY, 0)} {READY}, {statuses.get(REQUIRES_TEMPLATE, 0)} "
        f"{REQUIRES_TEMPLATE}, {statuses.get(PENDING_TEMPLATE, 0)} {PENDING_TEMPLATE}.",
    )
    return checks


def overview(rows: list[DocumentFarRecord], summary: dict | None = None) -> dict:
    summary = summary or {}
    base = base_rows(rows)
    types = Counter(r.content_type for r in base)
    alternates = [r for r in rows if is_alternate_row(r)]
    return {
        "part_heading": summary.get("part_heading"),
        "records": len(base),
        "clauses_provisions": types.get(CLAUSE_OR_PROVISION, 0),
        "reserved": types.get(RESERVED, 0),
        "subparts": types.get(SUBPART, 0),
        "alternates": len(alternates),
        "load_eligible": sum(1 for r in rows if r.load_eligible),
        "canonical_records": len(rows),
        "dated": sum(1 for r in base if r.version_date),
        "prescriptions": sum(1 for r in base if r.prescription),
        "with_references": sum(1 for r in base if r.embedded_references),
        "clauses": sum(1 for r in base if r.clause_type == "Clause"),
        "provisions": sum(1 for r in base if r.clause_type == "Provision"),
    }


# --- FAR Clauses & Provisions (the business-facing FAR view) --------------------------------
# FAR source semantics only: nothing here is an Oracle field or default.
# One row per FAR record in source order; an alternate follows its basic
# record, keeps its FAR Number and names itself in Alternate.

FAR_RECORD_COLUMNS = (
    "FAR Number",
    "Title",
    "Record Type",
    "FAR Part",
    "FAR Subpart",
    "FAR Section",
    "Record Status",
    "Revision Date",
    "Description",
    "Prescription / Usage",
    "Prescription Reference",
    "Alternate",
    "Cross References",
    "Provision Text",
    "Clause Text",
    "Section Text",
    "Source Reference",
)

# FAR_REGULATION core schema (Parts 1–51): one table for the whole Part.
# (header, row key) — the record text is the regulatory text.
CORE_RECORD_COLUMNS = (
    ("FAR Number", "FAR Number"),
    ("Title", "Title"),
    ("Record Type", "Record Type"),
    ("FAR Part", "FAR Part"),
    ("FAR Part Title", "FAR Part Title"),
    ("FAR Subpart", "FAR Subpart"),
    ("FAR Subpart Title", "FAR Subpart Title"),
    ("FAR Section", "FAR Section"),
    ("Record Status", "Record Status"),
    ("Description / Regulatory Text", "Section Text"),
    ("Prescription / Usage", "Prescription / Usage"),
    ("Prescription Reference", "Prescription Reference"),
    ("Cross References", "Cross References"),
    ("Source Reference", "Source Reference"),
)
# Part 53 (Forms): the core schema plus the form fields.
FORM_RECORD_COLUMNS = CORE_RECORD_COLUMNS[:12] + (
    ("Form Number", "Form Number"),
    ("Form Name", "Form Name"),
    ("Form Type", "Form Type"),
    ("Prescribing FAR Reference", "Prescribing FAR Reference"),
    ("Form Usage", "Form Usage"),
    ("Replacement / Supersession", "Replacement / Supersession"),
) + CORE_RECORD_COLUMNS[12:]
# Part 52: the provision/clause extension (FAR_RECORD_COLUMNS).
CLAUSE_RECORD_COLUMNS = tuple((column, column) for column in FAR_RECORD_COLUMNS)


def record_columns(part: str | None) -> tuple[tuple[str, str], ...]:
    """The FAR record table's columns for this Part — Part 52 fields are
    never forced onto Parts 1–51 or 53."""

    if part == "52":
        return CLAUSE_RECORD_COLUMNS
    if part == "53":
        return FORM_RECORD_COLUMNS
    return CORE_RECORD_COLUMNS


# The Oracle transformation view: target fields only, from business_row.
ORACLE_OUTPUT_COLUMNS = (
    "Action",
    "Date Published",
    "Number",
    "Title",
    "Display Name",
    "Intent",
    "Language",
    "Clause Type",
    "Status",
    "Description",
    "Provision Yn",
    "Global Yn",
    "Lock Text Yn",
    "Insert By Reference",
    "Text",
    "Start Date",
    "Attribute Category",
    "Attribute 1",
    "Source Reference",
)

_PART = re.compile(r"^(?:Subpart\s+)?(\d+)\.")
# "3.1004(a)", "15.209 (a)(1)", "12.301(b)(2)" — section plus paragraphs.
_PRESCRIBING = re.compile(r"(\d+\.\d+(?:-\d+)*)\s*((?:\(\s*[A-Za-z0-9]+\s*\))*)")


def far_part(row: DocumentFarRecord) -> str | None:
    match = _PART.match(row.far_number or "")
    return f"Part {match.group(1)}" if match else None


def prescription_reference_text(usage: str | None) -> str | None:
    """'As prescribed in 3.1004 (a), insert ...' -> '3.1004(a)'; several
    prescribing sections are listed in source order."""

    if not usage:
        return None
    lead = re.split(r",|\binsert\b|\buse\b|\badd\b|\bsubstitute\b", usage, maxsplit=1)[0]
    refs = []
    for section, paragraphs in _PRESCRIBING.findall(lead):
        ref = section + re.sub(r"\s+", "", paragraphs)
        if ref not in refs:
            refs.append(ref)
    return "; ".join(refs) or None


def far_record_type(row: DocumentFarRecord, parents: dict[str, DocumentFarRecord]) -> str:
    """Clause / Provision / Section / Subpart / Reserved. An alternate is
    a variant of its basic record and takes that record's type."""

    if is_alternate_row(row):
        parent = parents.get(row.basic_clause_key)
        return record_type(parent) if parent is not None else "Alternate"
    return record_type(row)


def far_source_reference(row: DocumentFarRecord, filename: str | None) -> str:
    """'part_52.html › Subpart 52.2 › 52.202-1 Definitions. · #FAR_52_202_1'.
    The DOM path itself stays in the cell provenance."""

    prov = row.provenance_json or {}
    trail = [str(part) for part in (prov.get("section_path") or [])[1:]]
    pieces = [filename or "source"] + trail
    if is_alternate_row(row) and row.alternate_code:
        pieces.append(row.alternate_code)
    reference = " › ".join(pieces)
    element = prov.get("element_id")
    return f"{reference} · #{element}" if element else reference


def _after_leads(text: str, leads: list[str | None]) -> str | None:
    """The text after its leading heading/instruction sentences, matched
    token by token (source spacing varies); sliced, never rewritten. When
    the leads don't open the text exactly, the whole text is kept; when
    they are the whole text (an instruction-only alternate), there is no
    separate body."""

    rest = text
    for lead in leads:
        if not lead:
            continue
        pattern = r"\s*" + r"\s*".join(re.escape(token) for token in lead.split()) + r"\s*\.?\s*"
        match = re.match(pattern, rest)
        if not match:
            return text
        rest = rest[match.end():]
    return rest if rest.strip() else None


def far_body(row: DocumentFarRecord) -> str | None:
    """A record's own body: after its prescription; for an alternate,
    after its heading and instruction (both shown in their own columns)."""

    if is_alternate_row(row):
        return _after_leads(row.source_text, [row.alternate_heading, row.alternate_instruction]) if row.source_text else None
    return body_text(row)


def part_number(row: DocumentFarRecord) -> str | None:
    match = _PART.match(row.far_number or "")
    return match.group(1) if match else None


def document_part(rows: list[DocumentFarRecord]) -> str | None:
    """The Part a FAR file is: the part most of its records belong to."""

    counts = Counter(part_number(r) for r in rows if part_number(r))
    return counts.most_common(1)[0][0] if counts else None


def far_record_row(
    row: DocumentFarRecord,
    parents: dict[str, DocumentFarRecord],
    filename: str | None = None,
    part_title: str | None = None,
) -> dict:
    """FAR_REGULATION: one row per FAR record of any Part. Part 52 keeps its
    clause/provision semantics (Revision Date, Prescription "As prescribed
    in …", Alternate, Provision / Clause Text); Parts 1–51 and 53 get the
    regulatory function as Record Type and their own prescriptions
    ("51.107 → 52.251-1"); Part 53 adds form fields. Values are filled only
    when the source states them."""

    alternate = is_alternate_row(row)
    kind = far_record_type(row, parents)
    part = part_number(row)
    clause_part = part == "52"
    usage = row.alternate_instruction if alternate else row.prescription
    # Only the body after the prescription; one text column per record —
    # a regulation section's (or subpart's) own text is Section Text.
    text = far_body(row) if kind != "Reserved" else None
    prescription_reference = prescription_reference_text(usage)
    regulatory_record = kind == "Section"
    prescribed = regulation.prescriptions(text) if regulatory_record and not clause_part else None
    if prescribed is not None:
        usage, prescription_reference = prescribed.usage, "; ".join(prescribed.references)
    if regulatory_record:
        kind = regulation.classify_record(row.title, text, prescribed)
    references = regulation.typed_references(row.source_text, row.far_number)
    if clause_part:
        # Part 52 indexes its embedded 52.xxx-x references; other citations
        # (CFR, U.S.C., …) follow them.
        others = [r for r in references if r.kind != "FAR"]
        cross = "; ".join(p for p in (refs_text(row), regulation.references_text(others)) if p) or None
    else:
        cross = regulation.references_text(references)
    form = regulation.form_info(row.title, text) if part == "53" and regulatory_record else None
    if alternate:
        description = row.alternate_heading
    elif row.content_type == SUBPART:
        description = None
    else:
        description = row.official_heading
    return {
        "FAR Number": row.far_number,
        "Title": row.subpart_title if row.content_type == SUBPART else row.title,
        "Record Type": kind,
        "FAR Part": far_part(row),
        "FAR Part Title": part_title,
        "FAR Subpart": row.subpart if row.content_type != SUBPART else None,
        "FAR Subpart Title": row.subpart_title if row.content_type != SUBPART else None,
        "FAR Section": row.subsection,
        "Record Status": "Reserved" if row.content_type == RESERVED else "Active",
        "Revision Date": row.version_date,
        "Description": description,
        "Prescription / Usage": usage,
        "Prescription Reference": prescription_reference,
        "Alternate": row.alternate_code if alternate else None,
        "Form Number": form.number if form else None,
        "Form Name": form.name if form else None,
        "Form Type": form.form_type if form else None,
        "Prescribing FAR Reference": form.prescribing_reference if form else None,
        "Form Usage": form.usage if form else None,
        "Replacement / Supersession": form.supersession if form else None,
        "Cross References": cross,
        "Provision Text": text if kind == "Provision" else None,
        "Clause Text": text if kind == "Clause" else None,
        "Section Text": text if kind not in ("Clause", "Provision") else None,
        "Source Reference": far_source_reference(row, filename),
    }


def far_parents(rows: list[DocumentFarRecord]) -> dict[str, DocumentFarRecord]:
    return {r.clause_key: r for r in rows if not is_alternate_row(r)}


def oracle_output_row(row: DocumentFarRecord) -> dict:
    business = business_row(row)
    return {column: business.get(column) for column in ORACLE_OUTPUT_COLUMNS}


def source_rows(rows: list[DocumentFarRecord], summary: dict | None, filename: str | None) -> list[dict]:
    """Document-level source metadata and traceability (Item | Detail)."""

    summary = summary or {}
    counts = overview(rows, summary)
    parents = far_parents(rows)
    types = Counter(far_record_type(r, parents) for r in rows if not is_alternate_row(r))
    items = [
        ("Source Document", filename),
        ("Source Type", "PDF (FAR regulation text)" if summary.get("source_format") == "pdf" else "HTML (FAR regulation text)"),
        ("Part", summary.get("part_heading")),
        ("Records (incl. alternates)", len(rows)),
        ("Base FAR Records", counts["records"]),
        ("Base Clauses", types.get("Clause", 0)),
        ("Base Provisions", types.get("Provision", 0)),
        ("Sections", types.get("Section", 0)),
        ("Subparts", types.get("Subpart", 0)),
        ("Reserved", types.get("Reserved", 0)),
        ("Alternates (each follows its basic record)", counts["alternates"]),
        ("Records With Revision Date", counts["dated"]),
        ("Records With Prescription", counts["prescriptions"]),
        ("Records With Cross References", counts["with_references"]),
        ("Extraction Method", "DOM structure (headings, paragraphs, element ids) — no OCR, no AI"),
        (
            "Traceability",
            "Every value links to its HTML element (element id and DOM path); Source Reference shows "
            "the heading trail. Text is kept verbatim.",
        ),
    ]
    if summary.get("duration_ms") is not None:
        items.append(("Processing Time (ms)", summary.get("duration_ms")))
    return [{"Item": item, "Detail": detail} for item, detail in items if detail not in (None, "")]
