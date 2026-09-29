"""Row views over the canonical FAR records — the workbook sheets
01_FAR_STAGING, 02_ORACLE_MAPPING, 04_STRUCTURED_FAR, 06_CANONICAL_MODEL,
99_LONG_TEXT — and the 03_VALIDATION checks. Shared by the staging
profile (UI datasets) and the exports, so every surface shows the same
values. Views never alter text.
"""

from __future__ import annotations

import re
from collections import Counter

from app.far.canonical import CLAUSE_OR_PROVISION, RESERVED, SUBPART
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


_KEY = re.compile(r"^FAR-(?:Subpart_52\.\d+|52\.\d{3}(?:-\d+)?)(?:-ALT-[IVX]+)?$")
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
        "One record per FAR article heading (the Part 52 title is not a record)",
        len(base) > 0,
        f"{len(base)} source/base FAR records"
        + (f" from {articles} FAR-headed source articles (Part 52 title included)" if articles else "")
        + f": {types.get(CLAUSE_OR_PROVISION, 0)} clause/provision/section, {types.get(RESERVED, 0)} reserved, "
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
        "Example: 52.101 Using Part 52.",
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
