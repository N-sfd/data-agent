"""far_part_52@1 — FAR Part 52 regulation staging profile.

    FAR HTML ─► DOM records (app/far/dom.py)
             ─► canonical FAR model, persisted (document_far_records)
             ─► staging datasets: FAR Sections (01), Clauses & Provisions
                (04), Alternates, FAR References, Canonical Model (06),
                Oracle Output Map (07 adapter spec), All Fields
             ─► validation (03) as QA rows; exports 01–07 + 99, CSV, JSON

Resolution needs strong structural evidence from the document itself (a
Part 52 heading or Subpart 52.x headings, plus many numbered FAR headings
opening their own sections); a contract that merely cites FAR clauses, or
a file merely named "part_52", is never recognized. Deterministic — no AI.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.far import exports as far_exports
from app.far import views
from app.far.canonical import (
    CLAUSE_OR_PROVISION,
    PROVENANCE_KEY,
    SUBPART,
    load_far_records,
    materialize_far_records,
)
from app.far.dom import recognize_far_part_52
from app.far.oracle_map import record_routing
from app.models.document import Document
from app.models.document_far_record import DocumentFarRecord
from app.services.document_storage import ensure_local_copy
from app.staging.models import (
    CellProvenance,
    ExportCapability,
    SourceLocator,
    ValidationCheck,
)
from app.staging.profile import (
    AdapterResult,
    DatasetDefinition,
    ExportArtifact,
    FieldDefinition,
    RawRecord,
    Recognition,
    StagingProfile,
)
from app.staging.provenance import make_provenance, system_provenance
from app.staging.validation import value_in_evidence

F = FieldDefinition
FAMILY = "far_regulation"
_HTML_SUFFIXES = {".html", ".htm"}
_EVIDENCE_CHARS = 300

OVERVIEW = DatasetDefinition(
    dataset_id="far_overview",
    display_name="Overview",
    cardinality="single",
    description="What this FAR Part 52 source contains, from its own structure.",
    fields=(
        F("far.part_heading", "part_heading", "Part Heading", expected=True),
        F("far.count.records", "records", "Source / Base FAR Records", "integer", grounding="system"),
        F("far.count.clauses_provisions", "clauses_provisions", "Clauses / Provisions / Sections", "integer", grounding="system"),
        F("far.count.clauses", "clauses", "Clauses", "integer", grounding="system"),
        F("far.count.provisions", "provisions", "Provisions", "integer", grounding="system"),
        F("far.count.reserved", "reserved", "Reserved Records", "integer", grounding="system"),
        F("far.count.subparts", "subparts", "Subparts", "integer", grounding="system"),
        F("far.count.alternates", "alternates", "Alternate Records (linked to base records)", "integer", grounding="system"),
        F("far.count.load_eligible", "load_eligible", "Load Eligible Records", "integer", grounding="system"),
        F("far.count.canonical_records", "canonical_records", "Canonical Records (base + alternates)", "integer", grounding="system"),
        F("far.count.dated", "dated", "Records With Revision Date", "integer", grounding="system"),
        F("far.count.prescriptions", "prescriptions", "Records With Prescription", "integer", grounding="system"),
        F("far.count.with_references", "with_references", "Records With Embedded FAR References", "integer", grounding="system"),
    ),
)

SECTIONS = DatasetDefinition(
    dataset_id="far_sections",
    display_name="FAR Sections",
    cardinality="repeating",
    description=(
        "01 FAR Staging — every FAR record in source order: subparts, sections, provisions, clauses "
        "and reserved records. Structural alternates are listed under Alternates."
    ),
    identity_fields=("far.section.far_number", "far.section.far_number_title"),
    grid_fields=("far.section.far_number", "far.section.far_number_title", "far.section.section", "far.section.subsection", "far.section.content_type"),
    fields=(
        F("far.section.sequence_id", "sequence_id", "Sequence ID", grounding="system"),
        F("far.section.far_number", "far_number", "FAR Number", "code", expected=True),
        F("far.section.title_type", "title_type", "Title / Type", grounding="derived"),
        F("far.section.far_number_title", "far_number_title", "FAR # + Title", expected=True),
        F("far.section.subid", "subid", "SubID", grounding="derived"),
        F("far.section.subtitle", "subtitle", "Subtitle"),
        F("far.section.subid_subtitle", "subid_subtitle", "SubID + Subtitle", grounding="derived"),
        F("far.section.section_text", "section_text", "Actual Section Text", grounding="derived"),
        F("far.section.section", "section", "Section", grounding="derived"),
        F("far.section.subsection", "subsection", "Subsection", grounding="derived"),
        F("far.section.content_type", "content_type", "Type", grounding="derived"),
        F("far.section.paragraph", "paragraph", "Paragraph", grounding="none"),
        F("far.section.subparagraph", "subparagraph", "Subparagraph", grounding="none"),
    ),
)

CLAUSES = DatasetDefinition(
    dataset_id="far_clauses",
    display_name="Clauses & Provisions",
    cardinality="repeating",
    description=(
        "04 Structured FAR — load-eligible sections, provisions and clauses with official heading, "
        "revision date, prescription and embedded references. Headings keep their dates; text is verbatim."
    ),
    identity_fields=("far.clause.far_number", "far.clause.title"),
    grid_fields=("far.clause.far_number", "far.clause.title", "far.clause.official_heading", "far.clause.revision_date", "far.clause.clause_type"),
    fields=(
        F("far.clause.far_number", "far_number", "FAR Number", "code", expected=True),
        F("far.clause.title", "title", "Title", expected=True),
        F("far.clause.official_heading", "official_heading", "Official Heading"),
        F("far.clause.revision_date", "revision_date", "Revision", grounding="derived"),
        F("far.clause.clause_type", "clause_type", "Type", grounding="derived"),
        F("far.clause.far_number_title", "far_number_title", "FAR # + Title", expected=True),
        F("far.clause.clause_key", "clause_key", "Clause Key", grounding="derived"),
        F("far.clause.prescription", "prescription", "Prescription"),
        F("far.clause.prescription_reference", "prescription_reference", "Prescription Reference", "code"),
        F("far.clause.alternates", "alternates", "Structural Alternates", grounding="derived"),
        F("far.clause.embedded_references", "embedded_references", "Embedded FAR References", grounding="derived"),
        F("far.clause.section_text", "section_text", "Actual Section Text", grounding="derived", expected=True),
        F("far.clause.section", "section", "Section", grounding="derived"),
        F("far.clause.subsection", "subsection", "Subsection", grounding="derived"),
    ),
)

ALTERNATES = DatasetDefinition(
    dataset_id="far_alternates",
    display_name="Alternates",
    cardinality="repeating",
    description=(
        "Structural alternates only (an 'Alternate I (date).' heading opening a paragraph), each linked to "
        "its basic clause. Narrative mentions of alternates are not records."
    ),
    identity_fields=("far.alternate.far_number", "far.alternate.alternate_code"),
    grid_fields=(
        "far.alternate.far_number",
        "far.alternate.alternate_code",
        "far.alternate.alternate_date",
        "far.alternate.basic_clause_key",
        "far.alternate.load_eligible",
    ),
    fields=(
        F("far.alternate.far_number", "far_number", "FAR Number", "code", expected=True),
        F("far.alternate.alternate_code", "alternate_code", "Alternate", expected=True),
        F("far.alternate.alternate_date", "alternate_date", "Date", grounding="derived"),
        F("far.alternate.basic_clause_key", "basic_clause_key", "Basic Clause Key", grounding="derived"),
        F("far.alternate.content_type", "content_type", "Type", grounding="derived"),
        F("far.alternate.clause_key", "clause_key", "Clause Key", grounding="derived"),
        F("far.alternate.alternate_heading", "alternate_heading", "Alternate Heading"),
        F("far.alternate.alternate_instruction", "alternate_instruction", "Alternate Instruction"),
        F("far.alternate.prescription_reference", "prescription_reference", "Prescription Reference", "code"),
        F("far.alternate.embedded_references", "embedded_references", "Embedded FAR References", grounding="derived"),
        F("far.alternate.alternate_text", "alternate_text", "Alternate Text", grounding="derived"),
        F("far.alternate.load_eligible", "load_eligible", "Load Eligible", grounding="derived"),
        F("far.alternate.oracle_routing", "oracle_routing", "Oracle Routing", grounding="derived"),
    ),
)

REFERENCES = DatasetDefinition(
    dataset_id="far_references",
    display_name="FAR References",
    cardinality="repeating",
    description=(
        "Embedded 52.xxx-x cross-references — an index for search and linking. A reference never creates a record."
    ),
    identity_fields=("far.reference.from_far_number", "far.reference.far_number"),
    grid_fields=(
        "far.reference.from_far_number",
        "far.reference.far_number",
        "far.reference.in_source",
        "far.reference.clause_key",
    ),
    fields=(
        F("far.reference.from_far_number", "from_far_number", "In FAR Record", "code", grounding="derived"),
        F("far.reference.from_clause_key", "from_clause_key", "In Clause Key", grounding="derived"),
        F("far.reference.far_number", "far_number", "Referenced FAR Number", "code", expected=True),
        F("far.reference.in_source", "in_source", "Record In This Source", grounding="derived"),
        F("far.reference.clause_key", "clause_key", "Referenced Clause Key", grounding="derived"),
    ),
)

CANONICAL = DatasetDefinition(
    dataset_id="far_canonical",
    display_name="Canonical Model",
    cardinality="repeating",
    description=(
        "06 Canonical FAR model — system-neutral, stable keys. Alternates are separate records linked by "
        "Basic Clause Key; structural and reserved records are kept with Load Eligible = NO."
    ),
    identity_fields=("far.canonical.clause_key", "far.canonical.display_name"),
    grid_fields=(
        "far.canonical.clause_key",
        "far.canonical.far_number",
        "far.canonical.content_type",
        "far.canonical.version_date",
        "far.canonical.load_eligible",
    ),
    fields=(
        F("far.canonical.source_sequence_id", "source_sequence_id", "Source Sequence ID", grounding="system"),
        F("far.canonical.clause_key", "clause_key", "Clause Key", grounding="derived", expected=True),
        F("far.canonical.parent_clause_key", "parent_clause_key", "Parent Clause Key", grounding="derived"),
        F("far.canonical.far_number", "far_number", "FAR Number", "code", expected=True),
        F("far.canonical.content_type", "content_type", "Content Type", grounding="derived", expected=True),
        F("far.canonical.title", "title", "Title"),
        F("far.canonical.display_name", "display_name", "Display Name", grounding="derived"),
        F("far.canonical.version_date", "version_date", "Version Date", grounding="derived"),
        F("far.canonical.alternate_code", "alternate_code", "Alternate Code"),
        F("far.canonical.basic_clause_key", "basic_clause_key", "Basic Clause Key", grounding="derived"),
        F("far.canonical.prescription_reference", "prescription_reference", "Prescription Reference", "code"),
        F("far.canonical.source_order", "source_order", "Source Order", "integer", grounding="system"),
        F("far.canonical.load_eligible", "load_eligible", "Load Eligible", grounding="derived", expected=True),
        F("far.canonical.source_text", "source_text", "Source Text", grounding="derived"),
        F("far.canonical.embedded_references", "embedded_references", "Embedded FAR References", grounding="derived"),
        F("far.canonical.transformation_notes", "transformation_notes", "Transformation Notes", grounding="none"),
    ),
)

BUSINESS = DatasetDefinition(
    dataset_id="far_business",
    display_name="Business Export",
    cardinality="repeating",
    description=(
        "Final business columns for downstream use. Intent, Start Date, Attribute Category "
        "and Attribute 1 stay blank until an approved rule or Oracle template supports them."
    ),
    identity_fields=("far.business.number", "far.business.display_name"),
    grid_fields=(
        "far.business.date_published",
        "far.business.number",
        "far.business.title",
        "far.business.display_name",
        "far.business.provision",
        "far.business.clause",
        "far.business.clause_type",
        "far.business.reserved",
    ),
    fields=tuple(
        F(f"far.business.{key}", key, label, grounding="derived")
        for key, label in (
            ("date_published", "Date Published"),
            ("number", "Number"),
            ("title", "Title"),
            ("display_name", "Display Name"),
            ("provision", "Provision"),
            ("clause", "Clause"),
            ("clause_type", "Clause Type"),
            ("reserved", "Reserved"),
            ("description", "Description"),
            ("text", "Text"),
            ("intent", "Intent"),
            ("start_date", "Start Date"),
            ("attribute_category", "Attribute Category"),
            ("attribute_1", "Attribute 1"),
            ("source_reference", "Source Reference"),
        )
    ),
)

OUTPUT_MAP = DatasetDefinition(
    dataset_id="far_oracle_output_map",
    display_name="Oracle Output Map",
    cardinality="repeating",
    role="source",
    description=(
        "Oracle Output Mapping — adapter specification (not a final Oracle import file). Canonical fields map "
        "to Oracle output concepts; exact import field names are bound only when the target Oracle Fusion "
        "template/schema is supplied."
    ),
    identity_fields=("far.map.canonical_field",),
    fields=(
        F("far.map.canonical_field", "canonical_field", "Canonical Field", grounding="none"),
        F("far.map.purpose", "purpose", "Purpose", grounding="none"),
        F("far.map.oracle_concept", "oracle_concept", "Oracle Output Concept", grounding="none"),
        F("far.map.rule", "rule", "Transformation Rule", grounding="none"),
        F("far.map.load_condition", "load_condition", "Load Condition", grounding="none"),
        F("far.map.source_field", "source_field", "Source / Canonical Field", grounding="none"),
        F("far.map.example", "example", "Example", grounding="none"),
        F("far.map.status", "status", "Implementation Status", grounding="none"),
    ),
)

ALL_FIELDS = DatasetDefinition(
    dataset_id="all_fields",
    display_name="All Fields",
    cardinality="repeating",
    description=(
        "Every structured FAR field found, one row per value, each with its own DOM evidence. Full texts are "
        "in Clauses & Provisions, Alternates and Canonical Model."
    ),
    identity_fields=("far.field.category", "far.field.name", "far.field.value"),
    grid_fields=("far.field.category", "far.field.name", "far.field.value"),
    fields=(
        F("far.field.category", "category", "Category", grounding="none"),
        F("far.field.name", "name", "Field", grounding="none"),
        # Literal values are checked against their evidence per row
        # (grounded_in_evidence); normalized ones (dates, types, keys) are
        # derived — see _all_field_records.
        F("far.field.value", "value", "Value", expected=True, grounding="derived"),
    ),
)

SOURCE_DOCUMENTS = DatasetDefinition(
    dataset_id="source_documents",
    display_name="Source Documents",
    cardinality="repeating",
    role="source",
    identity_fields=("source.document",),
    fields=(
        F("source.document", "source_document", "Source Document", grounding="none"),
        F("source.role", "role", "Role", grounding="none"),
        F("source.extraction_method", "extraction_method", "Extraction Method", grounding="none"),
        F("source.extraction_status", "extraction_status", "Extraction Status", grounding="none"),
        F("source.processing_ms", "processing_ms", "Processing Time (ms)", "integer", grounding="none"),
    ),
)

QA_REVIEW = DatasetDefinition(
    dataset_id="qa_review",
    display_name="QA Review",
    cardinality="repeating",
    role="qa",
    identity_fields=("qa.check", "qa.details"),
    fields=(
        F("qa.check", "qa_check", "QA Check", grounding="none"),
        F("qa.result", "result", "Result", grounding="none"),
        F("qa.details", "details", "Details", grounding="none"),
        F("qa.action", "action", "Action", grounding="none"),
    ),
)


# --- recognition -----------------------------------------------------------------------------


def recognize_far_document(database: Session, document: Document) -> Recognition:
    if Path(document.stored_filename or "").suffix.lower() not in _HTML_SUFFIXES:
        return Recognition(0.0, ["not an HTML source"])
    try:
        raw = ensure_local_copy(get_settings(), stored_filename=document.stored_filename).read_bytes()
    except Exception:
        return Recognition(0.0, ["source file unavailable"])
    # Cheap pre-check before parsing: FAR Part 52 structure markers.
    if b"52." not in raw or (b"Subpart" not in raw and b"Part 52" not in raw):
        return Recognition(0.0, ["no FAR Part 52 structure markers"])
    recognition = recognize_far_part_52(raw)
    return Recognition(recognition.score, recognition.reasons)


# --- adapter ---------------------------------------------------------------------------------


def _locator(row: DocumentFarRecord, dom_path: str | None = None) -> SourceLocator:
    prov = row.provenance_json or {}
    return SourceLocator(
        dom_path=dom_path or prov.get("dom_path"),
        element_id=prov.get("element_id"),
        section_path=list(prov.get("section_path") or []),
    )


def _prov(
    document: Document,
    row: DocumentFarRecord,
    evidence: str | None,
    dom_path: str | None = None,
    *,
    excerpt: bool = False,
) -> CellProvenance | None:
    """Evidence is the source element's own text. A whole-record text
    (derived: the record's blocks) is evidenced by its opening excerpt; a
    literal value's evidence is never shortened."""

    if not evidence:
        return None
    if excerpt and len(evidence) > _EVIDENCE_CHARS:
        evidence = evidence[:_EVIDENCE_CHARS]
    provenance = make_provenance(
        document,
        page=None,
        evidence=evidence,
        extraction_method="far_dom",
        locator=_locator(row, dom_path),
        anchor=(row.heading_text or row.far_number)[:80],
        source_type="html",
    )
    # The highlight is the evidence element itself — set here so the engine
    # never scans a 40,000-character clause text for a literal match.
    provenance.highlight_text = evidence.split("\n", 1)[0] if excerpt else evidence
    return provenance


def _heading_evidence(row: DocumentFarRecord) -> str:
    return row.heading_text or row.far_number


# --- derivation checks ---------------------------------------------------------------------
# Derived values (normalized dates, prescribing section, clause/provision
# type) are Verified only when the deterministic rule has exactly one
# answer in the retained source evidence; otherwise Needs Review. Agreement
# with any reference workbook is never an input.

_DATE_PAREN = re.compile(r"\(\s*[A-Za-z]{3,9}\.?\s*\d{4}\s*\)")
_SECTION_REF = re.compile(r"\d+\.\d+(?:-\d+)*")
_KIND = re.compile(r"\b(provision|clause)s?\b", re.I)
_END_OF = re.compile(r"^\(End of (provision|clause)\)$", re.I | re.M)


def _check(name: str, ok: bool, message: str) -> ValidationCheck:
    return ValidationCheck(check=name, passed=ok, message=None if ok else message)


def _date_check(date: str | None, evidence: str | None) -> list[ValidationCheck]:
    """Month YYYY from a heading: the heading has exactly one (Month YYYY)
    and the value's month and year are that one."""

    if not date or not evidence:
        return []
    month, _, year = date.partition(" ")
    dates = _DATE_PAREN.findall(evidence)
    return [
        _check(
            "date_in_heading",
            len(dates) == 1 and year in dates[0] and month[:3].casefold() in dates[0].casefold(),
            "The heading does not carry exactly one (Month YYYY) matching this date.",
        )
    ]


def _prescription_lead(text: str) -> str:
    """"As prescribed in 32.205(b) and 32.206, insert ..." -> the part naming
    the prescribing section(s)."""

    return re.split(r",|\binsert\b|\buse\b|\badd\b|\bsubstitute\b", text, maxsplit=1)[0]


def _prescription_reference_check(reference: str | None, prescription: str | None) -> list[ValidationCheck]:
    if not reference or not prescription:
        return []
    refs = set(_SECTION_REF.findall(_prescription_lead(prescription)))
    return [
        _check(
            "single_prescribing_section",
            refs == {reference},
            "The prescription names more than one prescribing section; confirm which applies."
            if len(refs) > 1
            else "The prescribing section could not be confirmed in the prescription text.",
        )
    ]


def _clause_type_check(row: DocumentFarRecord) -> list[ValidationCheck]:
    """Clause / Provision: the prescription's "insert the following X" and
    the record's own "(End of X)" marker must name one kind."""

    if not row.clause_type:
        return []
    kinds: set[str] = set()
    if row.prescription:
        head = row.prescription.split(":", 1)[0]
        insert = re.search(r"\b(?:insert|use)\b(.*)", head, re.I)
        kinds |= {k.lower() for k in _KIND.findall(insert.group(1) if insert else head)}
    kinds |= {k.lower() for k in _END_OF.findall(row.source_text or "")}
    return [
        _check(
            "unambiguous_clause_type",
            kinds == {row.clause_type.lower()},
            "The source names this record both a clause and a provision (prescription vs. end marker); confirm its type.",
        )
    ]


def _status(row: DocumentFarRecord) -> str | None:
    return "Needs Review" if row.issues else None


def _references_evidence(row: DocumentFarRecord, window: int = 60) -> str:
    """Each embedded reference in its own words: "… (see 52.104) …"."""

    text = row.source_text or ""
    snippets = []
    for ref in row.embedded_references or []:
        match = re.search(r"(?<![\d.])" + re.escape(ref) + r"(?!\d)(?!-\d)", text)
        if match:
            snippet = text[max(0, match.start() - window) : match.end() + window].replace("\n", " ").strip()
            snippets.append(f"… {snippet} …")
    return "\n".join(snippets)


def _base_cell_provenance(document: Document, row: DocumentFarRecord) -> dict[str, CellProvenance]:
    prov = row.provenance_json or {}
    heading = _prov(document, row, _heading_evidence(row), prov.get("heading_dom_path"))
    cells: dict[str, CellProvenance] = {}
    if row.official_heading:
        cells["official_heading"] = _prov(document, row, row.official_heading, prov.get("official_heading_dom_path"))
        cells["revision_date"] = cells["official_heading"]
        cells["subtitle"] = cells["official_heading"]
    if row.prescription:
        cells["prescription"] = _prov(document, row, row.prescription, prov.get("prescription_dom_path"))
        cells["prescription_reference"] = cells["prescription"]
    if row.clause_type and prov.get("clause_type_evidence"):
        cells["clause_type"] = _prov(document, row, prov["clause_type_evidence"])
    if row.source_text:
        cells["section_text"] = _prov(document, row, row.source_text, excerpt=True)
        cells["source_text"] = cells["section_text"]
    if row.embedded_references and row.source_text:
        cells["embedded_references"] = _prov(document, row, _references_evidence(row), prov.get("dom_path"))
    if row.content_type == SUBPART and row.subpart_title:
        cells["subtitle"] = heading
    return {k: v for k, v in cells.items() if v is not None} | {"_default": heading}


def _raw(record_id: str, values: dict, cells: dict[str, CellProvenance], row: DocumentFarRecord, checks=None) -> RawRecord:
    default = cells.pop("_default", None)
    return RawRecord(
        record_id=record_id,
        values=values,
        provenance=default,
        cell_provenance=cells,
        builder_status=_status(row),
        cell_checks=checks or {},
    )


def _section_record(document: Document, row: DocumentFarRecord) -> RawRecord:
    staging = views.staging_row(row)
    return _raw(
        f"far_sections:{row.clause_key}",
        {
            "sequence_id": staging["Sequence ID"],
            "far_number": row.far_number,
            "title_type": staging["Title / Type"],
            "far_number_title": staging["FAR # + Title"],
            "subid": staging["SubID"],
            "subtitle": staging["Subtitle"],
            "subid_subtitle": staging["SubID + Subtitle"],
            "section_text": staging["Actual Section Text"],
            "section": staging["Section"],
            "subsection": staging["Subsection"],
            "content_type": row.content_type,
        },
        _base_cell_provenance(document, row),
        row,
    )


def _alternates_of(row: DocumentFarRecord, alternates: dict[str, list[DocumentFarRecord]]) -> str | None:
    items = alternates.get(row.clause_key) or []
    return "; ".join(f"{a.alternate_code} ({a.version_date})" if a.version_date else a.alternate_code for a in items) or None


def _clause_record(document: Document, row: DocumentFarRecord, alternates: dict[str, list[DocumentFarRecord]]) -> RawRecord:
    cells = _base_cell_provenance(document, row)
    return _raw(
        f"far_clauses:{row.clause_key}",
        {
            "far_number": row.far_number,
            "title": row.title,
            "official_heading": row.official_heading,
            "revision_date": row.version_date,
            "clause_type": row.clause_type,
            "far_number_title": row.display_name,
            "clause_key": row.clause_key,
            "prescription": row.prescription,
            "prescription_reference": row.prescription_reference,
            "alternates": _alternates_of(row, alternates),
            "embedded_references": views.refs_text(row),
            "section_text": row.source_text,
            "section": row.subpart,
            "subsection": row.subsection,
        },
        cells,
        row,
        {
            "revision_date": _date_check(row.version_date, row.official_heading),
            "prescription_reference": _prescription_reference_check(row.prescription_reference, row.prescription),
            "clause_type": _clause_type_check(row),
        },
    )


def _alternate_cells(document: Document, row: DocumentFarRecord) -> dict[str, CellProvenance]:
    """An alternate's own values point at its heading paragraph; values it
    shares with its basic clause (FAR number, title) at the clause heading."""

    prov = row.provenance_json or {}
    evidence = row.alternate_heading if not row.alternate_instruction else f"{row.alternate_heading}. {row.alternate_instruction}"
    heading = _prov(document, row, evidence, prov.get("dom_path"))
    cells = {
        key: heading
        for key in ("alternate_code", "alternate_date", "version_date", "alternate_heading", "alternate_instruction", "prescription_reference")
    }
    if row.source_text:
        cells["alternate_text"] = cells["source_text"] = _prov(document, row, row.source_text, prov.get("dom_path"), excerpt=True)
    cells["_default"] = _prov(document, row, _heading_evidence(row), prov.get("record_dom_path"))
    return cells


def _alternate_record(document: Document, row: DocumentFarRecord) -> RawRecord:
    cells = _alternate_cells(document, row)
    return _raw(
        f"far_alternates:{row.clause_key}",
        {
            "far_number": row.far_number,
            "alternate_code": row.alternate_code,
            "alternate_date": row.version_date,
            "basic_clause_key": row.basic_clause_key,
            "content_type": row.content_type,
            "clause_key": row.clause_key,
            "alternate_heading": row.alternate_heading,
            "alternate_instruction": row.alternate_instruction,
            "prescription_reference": row.prescription_reference,
            "embedded_references": views.refs_text(row),
            "alternate_text": row.source_text,
            "load_eligible": "YES" if row.load_eligible else "NO",
            "oracle_routing": " / ".join(record_routing(row.content_type)),
        },
        cells,
        row,
        {
            "alternate_date": _date_check(row.version_date, row.alternate_heading),
            "prescription_reference": _prescription_reference_check(row.prescription_reference, row.alternate_instruction),
        },
    )


def _business_record(document: Document, row: DocumentFarRecord) -> RawRecord:
    exported = views.business_row(row)
    keys = [field.key for field in BUSINESS.fields]
    prov = row.provenance_json or {}
    locator = SourceLocator(
        dom_path=prov.get("dom_path"),
        element_id=prov.get("element_id"),
        section_path=list(prov.get("section_path") or []),
    )
    default = make_provenance(
        document,
        page=None,
        evidence=row.source_text or row.official_heading or row.far_number,
        extraction_method="dom",
        region_id=row.clause_key,
        anchor=row.official_heading or row.far_number,
        locator=locator,
        source_type="html",
    )
    return _raw(
        f"far_business:{row.clause_key}",
        dict(zip(keys, (exported[name] for name in views.BUSINESS_COLUMNS))),
        {"_default": default},
        row,
    )


def _canonical_record(document: Document, row: DocumentFarRecord) -> RawRecord:
    canonical = views.canonical_row(row)
    alternate = row.alternate_code is not None
    if alternate:
        cells = _alternate_cells(document, row)
    else:
        cells = _base_cell_provenance(document, row)
        cells["version_date"] = cells.get("official_heading", cells["_default"])
        if row.content_type == SUBPART:
            cells["title"] = cells["_default"]
    date_evidence = row.alternate_heading if alternate else row.official_heading
    return _raw(
        f"far_canonical:{row.clause_key}",
        {
            "source_sequence_id": canonical["Source Sequence ID"],
            "clause_key": canonical["Clause Key"],
            "parent_clause_key": canonical["Parent Clause Key"],
            "far_number": canonical["FAR Number"],
            "content_type": canonical["Content Type"],
            "title": canonical["Title"],
            "display_name": canonical["Display Name"],
            "version_date": canonical["Version Date"],
            "alternate_code": canonical["Alternate Code"],
            "basic_clause_key": canonical["Basic Clause Key"],
            "prescription_reference": canonical["Prescription Reference"],
            "source_order": canonical["Source Order"],
            "load_eligible": canonical["Load Eligible"],
            "source_text": canonical["Source Text"],
            "embedded_references": canonical["Embedded FAR References"],
            "transformation_notes": canonical["Transformation Notes"],
        },
        cells,
        row,
        {
            "version_date": _date_check(row.version_date, date_evidence),
            "prescription_reference": _prescription_reference_check(
                row.prescription_reference, row.alternate_instruction if alternate else row.prescription
            ),
        },
    )


_REFERENCE_WINDOW = 90


def _reference_records(document: Document, rows: list[DocumentFarRecord]) -> list[RawRecord]:
    keys = {r.far_number: r.clause_key for r in rows if r.alternate_code is None}
    records: list[RawRecord] = []
    for row in rows:
        text = row.source_text or ""
        for ref in row.embedded_references or []:
            match = re.search(r"(?<![\d.])" + re.escape(ref) + r"(?!\d)(?!-\d)", text)
            evidence = (
                text[max(0, match.start() - _REFERENCE_WINDOW) : match.end() + _REFERENCE_WINDOW].strip()
                if match
                else None
            )
            heading = _prov(document, row, _heading_evidence(row), (row.provenance_json or {}).get("heading_dom_path"))
            records.append(
                RawRecord(
                    record_id=f"far_references:{row.clause_key}:{ref}",
                    values={
                        "from_far_number": row.far_number,
                        "from_clause_key": row.clause_key,
                        "far_number": ref,
                        "in_source": "Yes" if ref in keys else "No",
                        "clause_key": keys.get(ref),
                    },
                    provenance=heading,
                    cell_provenance={"far_number": _prov(document, row, evidence)} if evidence else {},
                )
            )
    return records


_ALL_FIELD_KEYS = (
    ("far_number", "FAR Number"),
    ("title", "Title"),
    ("official_heading", "Official Heading"),
    ("version_date", "Revision Date"),
    ("clause_type", "Type"),
    ("prescription", "Prescription"),
    ("prescription_reference", "Prescription Reference"),
    ("alternate_code", "Alternate"),
    ("alternate_instruction", "Alternate Instruction"),
)


_DERIVED_KEYS = {"version_date", "clause_type", "content_type", "clause_key"}


def _field_checks(key: str, value, provenance: CellProvenance | None, row: DocumentFarRecord) -> list[ValidationCheck]:
    evidence = provenance.evidence_text if provenance else None
    if key == "version_date":
        return _date_check(value, evidence)
    if key == "clause_type":
        return _clause_type_check(row)
    if key == "prescription_reference":
        return _prescription_reference_check(
            value, row.alternate_instruction if row.alternate_code else row.prescription
        )
    if key in _DERIVED_KEYS or not evidence:
        return []
    grounded = value_in_evidence(value, evidence, "text")
    return [
        ValidationCheck(
            check="grounded_in_evidence",
            passed=grounded,
            message=None if grounded else "Value does not appear as-is in its source evidence.",
        )
    ]


def _all_field_records(document: Document, rows: list[DocumentFarRecord]) -> list[RawRecord]:
    records: list[RawRecord] = []
    for row in rows:
        category = row.display_name or row.far_number
        if row.alternate_code is None:
            cells = _base_cell_provenance(document, row)
            evidence_for = {
                "official_heading": cells.get("official_heading"),
                "version_date": cells.get("official_heading"),
                "prescription": cells.get("prescription"),
                "prescription_reference": cells.get("prescription"),
                "clause_type": cells.get("clause_type"),
            }
            default = cells["_default"]
        else:
            cells = _alternate_cells(document, row)
            evidence_for = {key: cells.get(key) for key in ("alternate_code", "alternate_instruction", "version_date", "prescription_reference")}
            default = cells["_default"]
        for key, label in _ALL_FIELD_KEYS:
            value = getattr(row, key)
            if value in (None, ""):
                continue
            if row.alternate_code is not None and key in ("title", "official_heading", "prescription", "clause_type"):
                continue
            provenance = evidence_for.get(key) or default
            records.append(
                RawRecord(
                    record_id=f"all_fields:{row.clause_key}:{key}",
                    values={"category": category, "name": label, "value": value},
                    provenance=provenance,
                    builder_status=_status(row),
                    cell_checks={"value": _field_checks(key, value, provenance, row)},
                )
            )
        if row.embedded_references:
            records.append(
                RawRecord(
                    record_id=f"all_fields:{row.clause_key}:embedded_references",
                    values={"category": category, "name": "Embedded FAR References", "value": views.refs_text(row)},
                    provenance=_prov(document, row, _references_evidence(row), (row.provenance_json or {}).get("dom_path")) or default,
                    builder_status=_status(row),
                )
            )
    return records


def adapt_far(database: Session, document: Document) -> AdapterResult:
    rows = load_far_records(database, document)
    summary = (document.ingestion_provenance or {}).get(PROVENANCE_KEY) or {}
    base = views.base_rows(rows)
    alternates: dict[str, list[DocumentFarRecord]] = {}
    for row in rows:
        if row.alternate_code is not None:
            alternates.setdefault(row.basic_clause_key, []).append(row)
    overview = views.overview(rows, summary)

    part_heading = summary.get("part_heading")
    overview_record = RawRecord(
        record_id="far_overview",
        values=overview,
        provenance=make_provenance(
            document,
            page=None,
            evidence=part_heading,
            extraction_method="far_dom",
            locator=SourceLocator(section_path=[part_heading] if part_heading else []),
            source_type="html",
        )
        if part_heading
        else None,
        cell_provenance={
            key: system_provenance(document)
            for key in overview
            if key != "part_heading"
        },
    )

    checks = views.validation_rows(rows, summary)
    qa_rows = [
        RawRecord(
            record_id=f"qa:far:{index}",
            values={
                "qa_check": check["Check"],
                "result": check["Result"],
                "details": check["Notes"],
                "action": "None." if check["Result"] == "PASS" else "Review against the source.",
            },
        )
        for index, check in enumerate(checks)
    ]

    records = {
        "far_overview": [overview_record],
        "far_sections": [_section_record(document, row) for row in base],
        "far_clauses": [_clause_record(document, row, alternates) for row in base if row.content_type == CLAUSE_OR_PROVISION],
        "far_alternates": [_alternate_record(document, row) for row in rows if row.alternate_code is not None],
        "far_references": _reference_records(document, rows),
        "far_canonical": [_canonical_record(document, row) for row in rows],
        "far_business": [_business_record(document, row) for row in rows],
        "far_oracle_output_map": [
            RawRecord(
                record_id=f"far_map:{index}",
                values={
                    "canonical_field": m["Canonical Field"],
                    "purpose": m["Purpose"],
                    "oracle_concept": m["Oracle Output Concept"],
                    "rule": m["Transformation Rule"],
                    "load_condition": m["Load Condition"],
                    "source_field": m["Source / Canonical Field"],
                    "example": m["Example"],
                    "status": m["Implementation Status"],
                },
            )
            for index, m in enumerate(views.output_map_rows())
        ],
        "all_fields": _all_field_records(document, rows),
        "source_documents": [
            RawRecord(
                record_id="source:primary",
                values={
                    "source_document": document.original_filename,
                    "role": "FAR regulation source (HTML)",
                    "extraction_method": "DOM (article/heading structure)",
                    "extraction_status": f"{len(base)} FAR records, {len(rows) - len(base)} alternates",
                    "processing_ms": summary.get("duration_ms"),
                },
            )
        ],
        "qa_review": qa_rows,
    }
    return AdapterResult(records=records, outcome_provenance=document.ingestion_provenance)


# --- exports ---------------------------------------------------------------------------------

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def export_far(database: Session, document: Document, export_id: str) -> ExportArtifact | None:
    rows = load_far_records(database, document)
    summary = (document.ingestion_provenance or {}).get(PROVENANCE_KEY) or {}
    stem = (document.original_filename or "far").rsplit(".", 1)[0]
    if export_id == "far_workbook.xlsx":
        return ExportArtifact(far_exports.build_far_workbook(rows, summary), _XLSX, f"{stem}_FAR_transformation.xlsx")
    if export_id == "far_canonical.json":
        payload = far_exports.build_far_json(
            rows, summary, {"id": document.id, "filename": document.original_filename}
        )
        return ExportArtifact(payload, "application/json", f"{stem}_FAR_canonical.json")
    if export_id.endswith(".csv") and export_id[:-4] in far_exports.CSV_SHEETS:
        sheet = export_id[:-4]
        return ExportArtifact(far_exports.build_far_csv(sheet, rows, summary), "text/csv", f"{stem}_{sheet}.csv")
    return None


def _export(capability_id: str, label: str, fmt: str, export_id: str) -> ExportCapability:
    return ExportCapability(
        capability_id=capability_id,
        label=label,
        format=fmt,
        href=f"/api/documents/{{document_id}}/staging-workbook/exports/{export_id}",
    )


FAR_PART_52_PROFILE = StagingProfile(
    profile_id="far_part_52",
    profile_version=1,
    display_name="FAR Part 52",
    description=(
        "FAR Part 52 regulation staging: grouped FAR records, structured clause/provision fields, "
        "structural alternates, embedded references, the canonical FAR model and the Oracle output "
        "mapping specification."
    ),
    document_families=(FAMILY,),
    datasets=(
        OVERVIEW,
        SECTIONS,
        CLAUSES,
        ALTERNATES,
        REFERENCES,
        CANONICAL,
        BUSINESS,
        OUTPUT_MAP,
        ALL_FIELDS,
        SOURCE_DOCUMENTS,
        QA_REVIEW,
    ),
    adapter=adapt_far,
    export_capabilities=(
        _export("far_workbook", "FAR Transformation Workbook (01–07, 99)", "xlsx", "far_workbook.xlsx"),
        _export("far_canonical_json", "Canonical FAR Model (JSON)", "json", "far_canonical.json"),
        *(
            _export("far_sheet_csv", f"{sheet} CSV", "csv", f"{sheet}.csv")
            for sheet in far_exports.CSV_SHEETS
        ),
    ),
    oracle_mapping_capability="planned",
    auto_qa_dataset="qa_review",
    source_structure="none",
    document_recognizer=recognize_far_document,
    contract_pipeline=False,
    materializer=materialize_far_records,
    exporter=export_far,
)

__all__ = ["FAR_PART_52_PROFILE"]
