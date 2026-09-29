"""FAR extraction → the system-neutral canonical FAR model, persisted per
document (document_far_records).

    Content Type          Load Eligible   Key
    CLAUSE_OR_PROVISION   YES             FAR-52.204-3
    RESERVED              NO              FAR-52.203-1
    SUBPART               NO              FAR-Subpart_52.1
    ALTERNATE             NO              FAR-52.215-1-ALT-I   (Basic Clause Key FAR-52.215-1)

An Alternate is its own record linked to the basic clause (Parent and
Basic Clause Key) — never flattened into the basic text and never loaded
until the Oracle alternate/variant template is bound (07 map: REQUIRES
ORACLE TEMPLATE). Nothing is discarded: basic text + alternate texts
reproduce the source record.
"""

from __future__ import annotations

import time

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.far.dom import EXTRACTOR_VERSION, FarExtraction, FarSourceRecord, extract_far
from app.models.document import Document
from app.models.document_far_record import DocumentFarRecord
from app.services.document_storage import ensure_local_copy
from app.services.ingestion_provenance import merge_provenance

CLAUSE_OR_PROVISION = "CLAUSE_OR_PROVISION"
RESERVED = "RESERVED"
SUBPART = "SUBPART"
ALTERNATE = "ALTERNATE"

NOTE_RESERVED = "Reserved source record; retain for traceability, exclude from load."
NOTE_EMBEDDED = "Contains embedded FAR cross-references; do not create master rows from references."
NOTE_STRUCTURAL = "Structural heading only."
NOTE_ALTERNATE = (
    "Structural alternate of {basic}; linked by Basic Clause Key. Exclude from load until the "
    "Oracle alternate/variant template is bound."
)
NOTE_RESERVED_ALTERNATE = "Reserved alternate placeholder of {basic}; retain for traceability, exclude from load."
NOTE_HAS_ALTERNATES = "Has {count} structural alternate(s) ({codes}), held as separate canonical records."

PROVENANCE_KEY = "far_part_52"


def clause_key(far_number: str) -> str:
    return "FAR-" + far_number.replace("Subpart ", "Subpart_")


def alternate_key(basic_key: str, roman: str) -> str:
    return f"{basic_key}-ALT-{roman}"


def _display(record: FarSourceRecord) -> str:
    heading = record.heading_text
    return heading[:-1].rstrip() if heading.endswith(".") and not heading.endswith("...") else heading


def build_canonical(extraction: FarExtraction, document_id: str) -> list[DocumentFarRecord]:
    rows: list[DocumentFarRecord] = []
    order = 0
    for record in extraction.records:
        key = clause_key(record.far_number)
        if record.kind == "subpart":
            content_type, load, notes = SUBPART, False, [NOTE_STRUCTURAL]
        elif record.kind == "reserved":
            content_type, load, notes = RESERVED, False, [NOTE_RESERVED]
        else:
            content_type, load, notes = CLAUSE_OR_PROVISION, True, []
        if record.basic_embedded_references:
            notes.append(NOTE_EMBEDDED)
        if record.alternates:
            notes.append(
                NOTE_HAS_ALTERNATES.format(
                    count=len(record.alternates),
                    codes=", ".join(a.code for a in record.alternates),
                )
            )
        order += 1
        locator = {
            "dom_path": record.dom_path,
            "element_id": record.element_id,
            "section_path": record.section_path,
            "heading_dom_path": record.heading_dom_path,
            "official_heading_dom_path": record.official_heading_dom_path,
            "prescription_dom_path": record.prescription_dom_path,
            "clause_type_evidence": record.clause_type_evidence,
            "source_char_count": record.source_char_count,
            "rendered_char_count": record.rendered_char_count,
            "grouped_text_length": len(record.grouped_text),
            # Non-whitespace characters of the whole record (basic +
            # alternates): the split is lossless when the parts add up.
            "grouped_nonspace_chars": len("".join(record.grouped_text.split())),
            "narrative_alternate_mentions": record.narrative_alternate_mentions,
        }
        rows.append(
            DocumentFarRecord(
                document_id=document_id,
                extractor_version=EXTRACTOR_VERSION,
                clause_key=key,
                parent_clause_key=None,
                basic_clause_key=key,
                source_sequence_id=str(record.sequence),
                source_order=order,
                content_type=content_type,
                load_eligible=load,
                far_number=record.far_number,
                title=record.title,
                heading_text=record.heading_text,
                display_name=_display(record),
                official_heading=record.official_heading,
                version_date=record.revision_date,
                clause_type=record.clause_type,
                prescription=record.prescription,
                prescription_reference=record.prescription_reference,
                alternate_code=None,
                alternate_heading=None,
                alternate_instruction=None,
                subpart=record.subpart,
                subpart_title=record.subpart_title,
                section_group=record.section_group,
                subsection=record.subsection,
                source_text=record.basic_text or None,
                embedded_references=list(record.basic_embedded_references),
                transformation_notes=" ".join(notes) or None,
                provenance_json=locator,
                issues=list(record.issues),
            )
        )
        for index, alternate in enumerate(record.alternates, start=1):
            order += 1
            alt_notes = [
                (NOTE_RESERVED_ALTERNATE if alternate.reserved else NOTE_ALTERNATE).format(basic=key)
            ]
            if alternate.embedded_references:
                alt_notes.append(NOTE_EMBEDDED)
            rows.append(
                DocumentFarRecord(
                    document_id=document_id,
                    extractor_version=EXTRACTOR_VERSION,
                    clause_key=alternate_key(key, alternate.roman),
                    parent_clause_key=key,
                    basic_clause_key=key,
                    source_sequence_id=f"{record.sequence}-A{index}",
                    source_order=order,
                    content_type=RESERVED if alternate.reserved else ALTERNATE,
                    load_eligible=False,
                    far_number=record.far_number,
                    title=record.title,
                    heading_text=record.heading_text,
                    display_name=f"{_display(record)} {alternate.heading}",
                    official_heading=record.official_heading,
                    version_date=alternate.date,
                    clause_type=record.clause_type,
                    prescription=None,
                    prescription_reference=alternate.prescription_reference,
                    alternate_code=alternate.code,
                    alternate_heading=alternate.heading,
                    alternate_instruction=alternate.instruction or None,
                    subpart=record.subpart,
                    subpart_title=record.subpart_title,
                    section_group=record.section_group,
                    subsection=record.subsection,
                    source_text=alternate.text or None,
                    embedded_references=list(alternate.embedded_references),
                    transformation_notes=" ".join(alt_notes),
                    provenance_json={
                        "dom_path": alternate.dom_path,
                        "element_id": alternate.element_id,
                        "section_path": [*record.section_path, alternate.heading],
                        "record_dom_path": record.dom_path,
                        "record_element_id": record.element_id,
                        "reserved_alternate": alternate.reserved,
                    },
                    issues=[],
                )
            )
    return rows


def _source_bytes(document: Document) -> bytes:
    return ensure_local_copy(get_settings(), stored_filename=document.stored_filename).read_bytes()


def materialize_far_records(database: Session, document: Document) -> dict:
    """(Re)builds the document's canonical FAR records; commits. Returns
    the run summary also stored in the document's ingestion provenance."""

    started = time.perf_counter()
    extraction = extract_far(_source_bytes(document))
    parsed_ms = int((time.perf_counter() - started) * 1000)
    rows = build_canonical(extraction, document.id)
    database.execute(delete(DocumentFarRecord).where(DocumentFarRecord.document_id == document.id))
    database.add_all(rows)
    summary = {
        "extractor_version": EXTRACTOR_VERSION,
        "part_heading": extraction.part_heading,
        "articles": extraction.article_count,
        "records": len(extraction.records),
        "canonical_records": len(rows),
        "alternates": sum(1 for r in rows if r.alternate_code),
        "warnings": extraction.warnings,
        "extract_ms": parsed_ms,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    merge_provenance(document, {PROVENANCE_KEY: summary})
    database.commit()
    return summary


def load_far_records(database: Session, document: Document) -> list[DocumentFarRecord]:
    """The document's canonical FAR records in source order — rebuilt when
    absent or produced by an older extractor."""

    rows = list(
        database.scalars(
            select(DocumentFarRecord)
            .where(DocumentFarRecord.document_id == document.id)
            .order_by(DocumentFarRecord.source_order)
        )
    )
    if not rows or any(r.extractor_version != EXTRACTOR_VERSION for r in rows):
        materialize_far_records(database, document)
        rows = list(
            database.scalars(
                select(DocumentFarRecord)
                .where(DocumentFarRecord.document_id == document.id)
                .order_by(DocumentFarRecord.source_order)
            )
        )
    return rows
