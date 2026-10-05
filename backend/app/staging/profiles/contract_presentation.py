"""The contract's business presentation, built over the profile's own
records (never re-extracted):

- Contract Data: every extracted record — details, parties, CLINs,
  pricing/funding, performance, delivery, administration, sections,
  attachments, clauses — one row each, in the unified columns of the
  contract's subtype (DoD / UCF contract, OASIS+ IDIQ, SF 1442 award). Each
  value keeps the provenance and checks of the record it came from.
- Contract Summary: a compact dashboard (identification, award/parties,
  financial summary, period of performance, key administration, document
  statistics) — a few dozen rows, never a copy of the data.

For each category, the layout-built records (app/contract_structure) are
used when present; the V3 records only when they are not, so no record is
listed twice.
"""

from __future__ import annotations

import re

from app.contract_structure.forms import CONTACTS, CONTRACTOR, FINANCIAL, ISSUING_OFFICE, PERFORMANCE, SOLICITATION_AWARD
from app.models.document import Document
from app.staging.models import CellProvenance
from app.staging.profile import DatasetDefinition, FieldDefinition, RawRecord
from app.staging.provenance import make_provenance

F = FieldDefinition

# Every value slot any contract subtype shows: (key, grounding). Which
# slots a document shows, in which order and under which caption, is its
# subtype's column set (column_labels; labelled_columns_only).
_SLOTS = (
    ("section", "none"), ("record_type", "none"), ("record_id", "derived"), ("title", "derived"),
    ("value", "derived"), ("reference", "derived"), ("regulation", "derived"),
    ("incorporation_type", "derived"), ("effective_date", "derived"), ("alternate", "derived"),
    ("period_from", "derived"), ("period_to", "derived"), ("quantity_period", "derived"),
    ("pricing", "derived"), ("amount", "derived"), ("domain", "derived"), ("naics_psc", "derived"),
    ("clin", "derived"), ("pricing_type", "derived"), ("labor_rate", "derived"),
    ("requirement", "derived"), ("period", "derived"), ("clause_number", "derived"),
    ("attachment", "derived"), ("contract_number", "derived"), ("amendment", "derived"),
    ("party", "derived"), ("quantity", "derived"), ("unit", "derived"), ("unit_price", "derived"),
    ("performance", "derived"), ("clause_type", "derived"), ("signature", "derived"),
    ("source_section", "none"), ("source_reference", "none"),
)

DOD = "dod"
OASIS = "oasis"
SF1442 = "sf1442"

SUBTYPE_LABELS = {
    DOD: "DoD / UCF contract",
    OASIS: "OASIS+ IDIQ contract",
    SF1442: "SF 1442 award",
}

# Each subtype's Contract Data columns, in order: (slot, caption).
COLUMN_SETS: dict[str, tuple[tuple[str, str], ...]] = {
    DOD: (
        ("section", "Section"), ("record_type", "Record Type"), ("record_id", "Record ID"),
        ("title", "Field / Title"), ("value", "Description / Value"), ("reference", "Reference / PWS"),
        ("regulation", "Regulation"), ("incorporation_type", "Incorporation Type"),
        ("effective_date", "Effective Date"), ("alternate", "Alternate / Deviation"),
        ("period_from", "Period From"), ("period_to", "Period To"), ("quantity_period", "Quantity / Period"),
        ("pricing", "Pricing Arrangement"), ("amount", "Amount"), ("source_section", "Source Section"),
        ("source_reference", "Source Reference"),
    ),
    OASIS: (
        ("section", "Section"), ("record_type", "Record Type"), ("record_id", "Record ID"),
        ("title", "Title"), ("value", "Description / Text"), ("domain", "Domain"),
        ("naics_psc", "NAICS / PSC"), ("clin", "CLIN"), ("pricing_type", "Contract / Pricing Type"),
        ("labor_rate", "Labor / Rate Information"), ("requirement", "Requirement / Deliverable"),
        ("period", "Period / Frequency"), ("clause_number", "FAR / GSAR Number"),
        ("incorporation_type", "Incorporation Type"), ("effective_date", "Effective Date"),
        ("alternate", "Alternate / Deviation"), ("attachment", "Attachment"),
        ("source_section", "Source Section"), ("source_reference", "Source Reference"),
    ),
    SF1442: (
        ("section", "Section"), ("record_type", "Record Type"), ("record_id", "Record ID"),
        ("title", "Field / Title"), ("value", "Description / Text"),
        ("contract_number", "Solicitation / Contract Number"), ("amendment", "Amendment / Modification"),
        ("party", "Contractor / Government Party"), ("clin", "CLIN / Item Number"), ("quantity", "Quantity"),
        ("unit", "Unit"), ("unit_price", "Unit Price"), ("amount", "Amount"),
        ("performance", "Performance / Delivery"), ("clause_number", "FAR / DFARS Number"),
        ("clause_type", "Clause / Provision Type"), ("effective_date", "Effective Date"),
        ("alternate", "Alternate / Deviation"), ("signature", "Signature / Award Information"),
        ("source_section", "Source Section"), ("source_reference", "Source Reference"),
    ),
}

# Kept for callers that want the DoD captions (e.g. tests, exports).
DATA_COLUMNS = tuple((key, label, dict(_SLOTS)[key]) for key, label in COLUMN_SETS[DOD])


def column_labels(subtype: str) -> dict[str, str]:
    """Canonical field -> caption, in the subtype's column order."""

    return {f"contract.data.{key}": label for key, label in COLUMN_SETS[subtype]}


CONTRACT_DATA = DatasetDefinition(
    dataset_id="contract_data",
    display_name="Contract Data",
    cardinality="repeating",
    description=(
        "Everything extracted from the contract — overview, parties, CLINs, pricing and funding, performance, "
        "delivery, administration, sections, attachments and clauses — one record per row in the same columns. "
        "Text is verbatim; every value links to its page."
    ),
    identity_fields=("contract.data.section", "contract.data.record_id", "contract.data.title"),
    grid_fields=tuple(f"contract.data.{key}" for key, _ in _SLOTS),
    full_text_grid=True,
    counts_records=False,
    labelled_columns_only=True,
    fields=tuple(F(f"contract.data.{key}", key, key.replace("_", " ").title(), grounding=grounding) for key, grounding in _SLOTS),
)

CONTRACT_OVERVIEW = DatasetDefinition(
    dataset_id="contract_overview",
    display_name="Contract Summary",
    cardinality="repeating",
    description=(
        "The contract at a glance: identification, award and parties, financial summary, period of performance, "
        "key administration and document statistics."
    ),
    identity_fields=("contract.overview.group", "contract.overview.label"),
    full_text_grid=True,
    counts_records=False,
    fields=(
        F("contract.overview.group", "group", "Category", grounding="none"),
        F("contract.overview.label", "label", "Field", grounding="none"),
        F("contract.overview.value", "value", "Value", grounding="derived"),
    ),
)

# Unified sections, in reading order.
OVERVIEW = "Overview"
PARTIES = "Parties"
CLINS = "CLINs"
PRICING = "Pricing & Funding"
PERFORMANCE_SECTION = "Performance"
DELIVERY = "Delivery"
ADMINISTRATION = "Administration"
SECTIONS = "Contract Sections"
ATTACHMENTS = "Attachments"
FAR_CLAUSES = "FAR Clauses"
DFARS_CLAUSES = "DFARS Clauses"
OTHER_CLAUSES = "Other Clauses"
REFERENCES = "FAR References"
OTHER = "Other Fields"
SECTION_ORDER = (
    OVERVIEW, PARTIES, CLINS, PRICING, PERFORMANCE_SECTION, DELIVERY, ADMINISTRATION,
    SECTIONS, ATTACHMENTS, FAR_CLAUSES, DFARS_CLAUSES, OTHER_CLAUSES, REFERENCES, OTHER,
)

_DETAIL_SECTION = {
    SOLICITATION_AWARD: OVERVIEW,
    ISSUING_OFFICE: PARTIES,
    CONTRACTOR: PARTIES,
    CONTACTS: PARTIES,
    PERFORMANCE: PERFORMANCE_SECTION,
    FINANCIAL: PRICING,
}
# Fields whose meaning places them regardless of the form area they sit in.
_FIELD_SECTION = {
    "contract.administered_by": ADMINISTRATION,
    "contract.payment_office": ADMINISTRATION,
    "contract.invoice_address": ADMINISTRATION,
    "contract.accounting_data": ADMINISTRATION,
    "contract.contracting_officer": ADMINISTRATION,
    "contract.contract_vehicle": OVERVIEW,
    "contract.naics": OVERVIEW,
    "contract.size_standard": OVERVIEW,
    "contract.agency_office": PARTIES,
    "contract.base_period": PERFORMANCE_SECTION,
    "contract.options": PERFORMANCE_SECTION,
    "contract.max_duration": PERFORMANCE_SECTION,
    "contract.task_order_range": PRICING,
}


def _first_provenance(record: RawRecord, keys: tuple[str, ...] = ()) -> CellProvenance | None:
    for key in keys:
        if record.cell_provenance.get(key):
            return record.cell_provenance[key]
    return record.provenance or next(iter(record.cell_provenance.values()), None)


def _source_reference(filename: str, provenance: CellProvenance | None) -> str:
    page = provenance.source_page if provenance else None
    return f"{filename} · p. {page}" if page else filename


def _joined(*parts: object, separator: str = " ") -> str | None:
    text = separator.join(str(part).strip() for part in parts if part not in (None, "") and str(part).strip())
    return text or None


def _row(
    filename: str,
    section: str,
    record_type: str,
    source: RawRecord,
    values: dict[str, object],
    keymap: dict[str, str],
    *,
    source_section: str | None = None,
) -> RawRecord:
    """One unified row. `keymap` names, per unified column, the source
    record's key whose provenance and checks the value carries."""

    cell_provenance: dict[str, CellProvenance] = {}
    checks = {}
    for target, source_key in keymap.items():
        provenance = source.cell_provenance.get(source_key) or source.provenance
        if provenance is not None:
            cell_provenance[target] = provenance
        if source.cell_checks.get(source_key):
            checks[target] = source.cell_checks[source_key]
    main = _first_provenance(source, tuple(keymap.values()))
    return RawRecord(
        record_id=f"data:{source.record_id}",
        values={
            **values,
            "section": section,
            "record_type": record_type,
            "source_section": source_section,
            "source_reference": _source_reference(filename, main),
        },
        provenance=main,
        cell_provenance=cell_provenance,
        cell_checks=checks,
        builder_status=source.builder_status,
    )


_SLIN = re.compile(r"^\d{4}[A-Z]{2}$")
# "Period of Performance From 01 Oct 2024 To 31 Jul 2025" -> its two dates.
_PERIOD = re.compile(r"\bfrom\s+(.+?)\s+(?:to|through|thru)\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL)


def _clin_kind(number: str | None) -> str:
    return "SLIN" if number and _SLIN.match(number.strip()) else "CLIN"


def _regulation_section(regulation: str | None) -> str:
    regulation = (regulation or "").upper()
    if regulation.startswith("DFAR"):
        return DFARS_CLAUSES
    if regulation.startswith("FAR"):
        return FAR_CLAUSES
    return OTHER_CLAUSES


def contract_data_records(records: dict[str, list[RawRecord]], filename: str) -> list[RawRecord]:
    rows: list[RawRecord] = []

    for record in records.get("contract_details", []):
        v = record.values
        field_id = v.get("field_id") or ""
        section = _FIELD_SECTION.get(field_id) or _DETAIL_SECTION.get(v.get("section"), OVERVIEW)
        rows.append(
            _row(
                filename, section, "Field", record,
                {"record_id": field_id.removeprefix("contract.") or None, "title": v.get("label"), "value": v.get("value")},
                {"value": "value", "record_id": "value", "title": "value"},
                source_section=v.get("section"),
            )
        )

    # CLINs: the schedule's own line items, enriched from V3 (pricing type,
    # performance period) for the same CLIN number.
    v3_clins = {str(r.values.get("clin") or "").strip(): r for r in records.get("clins", [])}
    line_items = records.get("line_items", [])
    if line_items:
        for record in line_items:
            v = record.values
            number = v.get("item_number")
            v3 = v3_clins.get(str(number or "").strip())
            v3_values = v3.values if v3 else {}
            rows.append(
                _row(
                    filename, CLINS, _clin_kind(number), record,
                    {
                        "record_id": number,
                        "clin": number,
                        "title": (v.get("description") or "").split("\n", 1)[0] or None,
                        "value": v.get("description"),
                        "quantity": v.get("quantity"),
                        "unit": v.get("unit"),
                        "unit_price": v.get("unit_price"),
                        "pricing_type": v3_values.get("pricing_type"),
                        "naics_psc": v3_values.get("psc"),
                        "amount": v.get("amount"),
                        "period_from": v3_values.get("pop_start"),
                        "period_to": v3_values.get("pop_end"),
                    },
                    {"record_id": "item_number", "clin": "item_number", "title": "description", "value": "description",
                     "quantity": "quantity", "unit": "unit", "unit_price": "unit_price", "amount": "amount"},
                    source_section="Schedule of supplies / services",
                )
            )
    else:
        for record in records.get("clins", []):
            v = record.values
            rows.append(
                _row(
                    filename, CLINS, _clin_kind(v.get("clin")), record,
                    {
                        "record_id": v.get("clin"),
                        "clin": v.get("clin"),
                        "title": (v.get("description") or "").split("\n", 1)[0] or None,
                        "value": v.get("description"),
                        "quantity": v.get("max_quantity"),
                        "unit": v.get("unit"),
                        "unit_price": v.get("unit_price"),
                        "pricing_type": v.get("pricing_type"),
                        "naics_psc": v.get("psc"),
                        "amount": v.get("max_amount"),
                        "period_from": v.get("pop_start"),
                        "period_to": v.get("pop_end"),
                        "reference": v.get("purchase_request"),
                    },
                    {"record_id": "clin", "clin": "clin", "title": "description", "value": "description", "quantity": "max_quantity",
                     "unit": "unit", "unit_price": "unit_price", "pricing_type": "pricing_type", "naics_psc": "psc",
                     "amount": "max_amount", "period_from": "pop_start", "period_to": "pop_end", "reference": "purchase_request"},
                    source_section="CLIN schedule",
                )
            )

    for record in records.get("funding", []):
        v = record.values
        rows.append(
            _row(
                filename, PRICING, _joined("Funding", v.get("funding_level"), separator=" — ") or "Funding", record,
                {
                    "record_id": v.get("clin"),
                    "clin": v.get("clin"),
                    "title": v.get("funding_status"),
                    "value": v.get("accounting_appropriation"),
                    "reference": v.get("purchase_request"),
                    "amount": v.get("amount"),
                },
                {"record_id": "clin", "clin": "clin", "title": "funding_status", "value": "accounting_appropriation", "reference": "purchase_request", "amount": "amount"},
                source_section="Funding / accounting data",
            )
        )

    for record in records.get("performance_delivery", []):
        v = record.values
        rows.append(
            _row(
                filename, PERFORMANCE_SECTION, v.get("record_type") or "Performance", record,
                {
                    "record_id": v.get("clin"),
                    "clin": v.get("clin"),
                    "requirement": v.get("requirement"),
                    "value": v.get("requirement"),
                    "reference": v.get("location_destination"),
                    "period_from": v.get("start"),
                    "period_to": v.get("end_timing"),
                },
                {"record_id": "clin", "clin": "clin", "requirement": "requirement", "value": "requirement", "reference": "location_destination", "period_from": "start", "period_to": "end_timing"},
                source_section="Performance / delivery terms",
            )
        )

    for record in records.get("delivery_information", []):
        v = record.values
        when = v.get("delivery_date")
        period = _PERIOD.search(when or "")
        rows.append(
            _row(
                filename, DELIVERY, "Delivery", record,
                {
                    "record_id": v.get("clin"),
                    "clin": v.get("clin"),
                    # The printed delivery term stays visible as written.
                    "value": _joined(v.get("ship_to"), when if period else None, separator="\n"),
                    "reference": v.get("dodaac_cage"),
                    "period_from": period.group(1).strip() if period else None,
                    "period_to": period.group(2).strip() if period else when,
                    "quantity": v.get("quantity"),
                },
                {"record_id": "clin", "clin": "clin", "value": "ship_to" if v.get("ship_to") else "delivery_date", "reference": "dodaac_cage",
                 "period_from": "delivery_date", "period_to": "delivery_date", "quantity": "quantity"},
                source_section="Delivery schedule",
            )
        )

    for record in records.get("contract_sections", []):
        v = record.values
        rows.append(
            _row(
                filename, SECTIONS, "Section", record,
                {"record_id": v.get("number"), "title": v.get("title"), "value": v.get("text"), "reference": v.get("number")},
                {"record_id": "number", "title": "title", "value": "text", "reference": "number"},
                source_section=v.get("section"),
            )
        )
    for record in records.get("section_tables", []):
        v = record.values
        cells = [v.get(f"c{i}") for i in range(1, 9)]
        rows.append(
            _row(
                filename, SECTIONS, "Table Row", record,
                {"record_id": v.get("table_id"), "title": v.get("headers"), "value": _joined(*cells, separator=" | "),
                 **_table_slots(v.get("headers"), cells)},
                {"value": "c1"},
                source_section=_joined(v.get("section"), v.get("subsection"), separator=" › "),
            )
        )

    structure_attachments = records.get("contract_attachments", [])
    for record in structure_attachments:
        v = record.values
        rows.append(
            _row(
                filename, ATTACHMENTS, "Attachment", record,
                {"record_id": v.get("reference"), "title": v.get("title"), "reference": v.get("reference")},
                {"record_id": "reference", "title": "title", "reference": "reference"},
                source_section=_joined(v.get("section"), v.get("group"), separator=" › "),
            )
        )
    if not structure_attachments:
        for record in records.get("attachments", []):
            v = record.values
            rows.append(
                _row(
                    filename, ATTACHMENTS, "Attachment", record,
                    {"record_id": v.get("attachment_reference"), "title": v.get("title_description"), "reference": v.get("attachment_reference")},
                    {"record_id": "attachment_reference", "title": "title_description", "reference": "attachment_reference"},
                    source_section="List of attachments",
                )
            )

    structure_clauses = records.get("contract_clauses", [])
    for record in structure_clauses:
        v = record.values
        variation = f"Variation effective {v['variation_date']}" if v.get("variation_date") else None
        rows.append(
            _row(
                filename, _regulation_section(v.get("regulation")), "Clause", record,
                {
                    "record_id": v.get("clause_number"),
                    "title": v.get("title"),
                    "value": v.get("text"),
                    "regulation": v.get("regulation"),
                    "incorporation_type": v.get("incorporation_type"),
                    "effective_date": v.get("date"),
                    "alternate": _joined(v.get("alternate"), variation, separator="; "),
                },
                {"record_id": "clause_number", "title": "title", "value": "text", "regulation": "regulation",
                 "incorporation_type": "incorporation_type", "effective_date": "date", "alternate": "alternate"},
                source_section=v.get("contract_section") or v.get("source_heading"),
            )
        )
    if not structure_clauses:
        for dataset in ("clauses", "dfars"):
            for record in records.get(dataset, []):
                v = record.values
                rows.append(
                    _row(
                        filename, _regulation_section(v.get("regulation") or ("DFARS" if dataset == "dfars" else None)), "Clause", record,
                        {
                            "record_id": v.get("clause_number"),
                            "title": v.get("clause_title"),
                            "regulation": v.get("regulation"),
                            "incorporation_type": v.get("incorporation_type"),
                            "effective_date": v.get("effective_date"),
                            "alternate": v.get("alternate_deviation"),
                        },
                        {"record_id": "clause_number", "title": "clause_title", "regulation": "regulation",
                         "incorporation_type": "incorporation_type", "effective_date": "effective_date", "alternate": "alternate_deviation"},
                        source_section="Clauses",
                    )
                )

    for record in records.get("far_references", []):
        v = record.values
        rows.append(
            _row(
                filename, REFERENCES, v.get("reference_type") or "FAR Reference", record,
                {"record_id": v.get("far_reference"), "value": v.get("subject_context"), "regulation": "FAR", "reference": v.get("far_reference")},
                {"record_id": "far_reference", "value": "subject_context", "reference": "far_reference"},
                source_section="Mentioned in the text (not an incorporated clause)",
            )
        )

    # V3 label/value fields only when the forms gave no details (they repeat
    # the details under other names, or are fragments, when both exist).
    for record in [] if records.get("contract_details") else records.get("all_fields", []):
        v = record.values
        if not v.get("value"):
            continue
        rows.append(
            _row(
                filename, OTHER, "Field", record,
                {"title": v.get("normalized_field"), "value": v.get("value")},
                {"title": "normalized_field", "value": "value"},
                source_section=v.get("category"),
            )
        )

    for row in rows:
        _enrich(row)
    order = {name: index for index, name in enumerate(SECTION_ORDER)}
    rows.sort(key=lambda row: order.get(row.values["section"], len(order)))
    # Unique ids, stable across reads.
    for index, row in enumerate(rows):
        row.record_id = f"{row.record_id}:{index}"
    return rows


# --- subtype slots --------------------------------------------------------------------------

# A section table's own column headings -> the slot they fill.
_TABLE_HEADINGS = (
    (re.compile(r"\b(naics|psc|product service code)\b", re.I), "naics_psc"),
    (re.compile(r"\b(labor|rate|category|hourly|ceiling)\b", re.I), "labor_rate"),
    (re.compile(r"\b(deliverable|requirement|cdrl|report)\b", re.I), "requirement"),
    (re.compile(r"\b(frequency|due|schedule|period)\b", re.I), "period"),
    (re.compile(r"\b(clin|item)\b", re.I), "clin"),
    (re.compile(r"\bdomain\b", re.I), "domain"),
    (re.compile(r"\b(attachment|exhibit)\b", re.I), "attachment"),
)


def _table_slots(headers: str | None, cells: list) -> dict[str, str]:
    """Fill slots from a table row by its own headings: the cell under a
    'Labor Category' heading is labor/rate information, and so on."""

    names = [h.strip() for h in (headers or "").split("|")]
    slots: dict[str, list[str]] = {}
    for name, cell in zip(names, cells):
        if not cell:
            continue
        for pattern, slot in _TABLE_HEADINGS:
            if pattern.search(name):
                slots.setdefault(slot, []).append(f"{name}: {cell}" if slot in ("labor_rate", "requirement") else str(cell))
                break
    return {slot: "; ".join(values) for slot, values in slots.items()}


OASIS_DOMAINS = (
    "Management & Advisory", "Technical & Engineering", "Research & Development", "Intelligence Services",
    "Environmental", "Facilities", "Logistics", "Enterprise Solutions",
)
_DOMAIN_PATTERNS = tuple((name, re.compile(re.escape(name).replace("\\&", "(?:&|and)"), re.I)) for name in OASIS_DOMAINS)

# Contract / pricing types named in a record ("Firm-Fixed-Price",
# "Time-and-Materials"), as the source writes them.
PRICING_TYPES = (
    "Firm-Fixed-Price", "Fixed-Price Incentive", "Fixed-Price with Economic Price Adjustment",
    "Time-and-Materials", "Labor-Hour", "Cost-Plus-Fixed-Fee", "Cost-Plus-Award-Fee",
    "Cost-Plus-Incentive-Fee", "Cost-Reimbursement", "Cost-Sharing", "Cost-No-Fee",
)
_PRICING_PATTERNS = tuple(
    (name, re.compile(r"\b" + r"[\s-]+".join(re.escape(part) for part in re.split(r"[\s-]+", name)) + r"\b", re.I))
    for name in PRICING_TYPES
)

_END_OF = re.compile(r"\(End of (provision|clause)\)", re.I)
_PARTY_SECTIONS = {ISSUING_OFFICE, CONTRACTOR, CONTACTS}
_PARTY_IDS = {"contract.administered_by", "contract.payment_office", "contract.offeror", "contract.issued_by", "contract.cage", "contract.uei"}
_SIGNATURE_IDS = {
    "contract.award_date", "contract.award_amount", "contract.contracting_officer", "contract.offeror_signatory",
    "contract.offer_date", "contract.items_accepted", "contract.date_issued",
}
_PERFORMANCE_IDS = {"contract.performance_start", "contract.period_of_performance", "contract.place_of_performance", "contract.performance_period_type"}
_NUMBER_IDS = {"contract.contract_number", "contract.solicitation_number"}


def _copy(row: RawRecord, target: str, value: object, from_key: str = "value") -> None:
    if value in (None, "") or row.values.get(target):
        return
    row.values[target] = value
    provenance = row.cell_provenance.get(from_key) or row.provenance
    if provenance is not None:
        row.cell_provenance.setdefault(target, provenance)


def _enrich(row: RawRecord) -> None:
    """The subtype slots, from the row's own values: nothing new is read."""

    v = row.values
    kind = v.get("record_type")
    field_id = f"contract.{v['record_id']}" if kind == "Field" and v.get("record_id") else ""
    title = str(v.get("title") or "")

    if kind == "Clause":
        _copy(row, "clause_number", v.get("record_id"), "record_id")
        marker = _END_OF.search(str(v.get("value") or ""))
        provision = marker.group(1).title() if marker else None
        _copy(row, "clause_type", _joined(provision, v.get("incorporation_type"), separator=" · "), "incorporation_type")
    _copy(row, "quantity_period", _joined(v.get("quantity"), v.get("unit")), "quantity")
    _copy(row, "pricing", _joined(v.get("pricing_type"), f"Unit Price {v['unit_price']}" if v.get("unit_price") else None, separator="; "), "unit_price")
    if v.get("period_from") or v.get("period_to"):
        period = f"From {v['period_from']} to {v['period_to']}" if v.get("period_from") and v.get("period_to") else v.get("period_from") or v.get("period_to")
        _copy(row, "period", period, "period_to")
    if v["section"] == "Attachments":
        _copy(row, "attachment", _joined(v.get("reference"), v.get("title"), separator=" — "), "title")
    if v["section"] in ("Performance", "Delivery"):
        _copy(row, "performance", _joined(v.get("value"), v.get("period"), separator="; ") or v.get("period_to"), "value")

    if kind == "Field":
        value = v.get("value")
        if field_id in _NUMBER_IDS or re.search(r"\b(contract|solicitation)\s+no\b", title, re.I):
            _copy(row, "contract_number", value)
        if re.search(r"amend|modif", title + " " + field_id, re.I):
            _copy(row, "amendment", value)
        if v.get("source_section") in _PARTY_SECTIONS or field_id in _PARTY_IDS:
            _copy(row, "party", value)
        if field_id in _SIGNATURE_IDS or re.search(r"\bsign|award", title, re.I):
            _copy(row, "signature", value)
        if v.get("source_section") == PERFORMANCE or field_id in _PERFORMANCE_IDS:
            _copy(row, "performance", value)
        if field_id == "contract.naics" or re.search(r"\b(naics|psc)\b", title, re.I):
            _copy(row, "naics_psc", value)
        if re.search(r"contract type|type of contract|pricing", title, re.I):
            _copy(row, "pricing_type", value)

    text = " ".join(str(v.get(key) or "") for key in ("title", "value", "source_section"))
    domains = [name for name, pattern in _DOMAIN_PATTERNS if pattern.search(text)]
    if domains:
        _copy(row, "domain", "; ".join(domains))
    # Clause titles name pricing types ("Inspection of Supplies-Fixed-Price")
    # without making the contract one; only other records count.
    if kind not in ("Clause",) and v["section"] != "FAR References":
        named = [name for name, pattern in _PRICING_PATTERNS if pattern.search(text)]
        if named:
            _copy(row, "pricing_type", "; ".join(named))


def contract_subtype(page_text: str) -> str:
    """SF 1442 award, OASIS+ IDIQ, or a DoD / UCF contract — from the
    first pages' own text (form number, program name)."""

    if re.search(r"\b(SF|STANDARD FORM)\s*1442\b|\b1442\s*\(", page_text, re.I):
        return SF1442
    if re.search(r"\bOASIS\b", page_text):
        return OASIS
    return DOD


# --- Contract Summary ------------------------------------------------------------------------

IDENTIFICATION = "Contract Identification"
AWARD_PARTIES = "Award / Parties"
FINANCIAL_SUMMARY = "Financial Summary"
PERIOD = "Period of Performance"
KEY_ADMIN = "Key Administration"
STATISTICS = "Document Statistics"

# (group, label, detail field ids in preference order)
_SUMMARY_FIELDS = (
    (IDENTIFICATION, "Contract Number", ("contract.contract_number",)),
    (IDENTIFICATION, "Solicitation Number", ("contract.solicitation_number",)),
    (IDENTIFICATION, "Title / Description", ("contract.solicitation_title", "contract.description_scope")),
    (IDENTIFICATION, "Contract Vehicle", ("contract.contract_vehicle",)),
    (IDENTIFICATION, "Solicitation Type", ("contract.solicitation_type",)),
    (IDENTIFICATION, "Requisition / Purchase Request", ("contract.requisition_number",)),
    (IDENTIFICATION, "Project Number", ("contract.project_number",)),
    (IDENTIFICATION, "NAICS", ("contract.naics",)),
    (IDENTIFICATION, "Size Standard", ("contract.size_standard",)),
    (AWARD_PARTIES, "Award Date", ("contract.award_date",)),
    (AWARD_PARTIES, "Date Issued", ("contract.date_issued",)),
    (AWARD_PARTIES, "Issued By", ("contract.issued_by", "contract.agency_office")),
    (AWARD_PARTIES, "Contractor", ("contract.offeror", "contract.contractor")),
    (AWARD_PARTIES, "CAGE", ("contract.cage",)),
    (AWARD_PARTIES, "UEI", ("contract.uei",)),
    (AWARD_PARTIES, "Contracting Officer", ("contract.contracting_officer",)),
    (FINANCIAL_SUMMARY, "Award Amount", ("contract.award_amount",)),
    (FINANCIAL_SUMMARY, "Ceiling / Max Aggregate", ("contract.ceiling_max_aggregate",)),
    (FINANCIAL_SUMMARY, "Minimum Guarantee", ("contract.minimum_guarantee",)),
    (FINANCIAL_SUMMARY, "Task Order Range", ("contract.task_order_range",)),
    (PERIOD, "Performance Start", ("contract.performance_start",)),
    (PERIOD, "Period of Performance", ("contract.period_of_performance",)),
    (PERIOD, "Performance Period Type", ("contract.performance_period_type",)),
    (PERIOD, "Base Period", ("contract.base_period",)),
    (PERIOD, "Options", ("contract.options",)),
    (PERIOD, "Max Duration", ("contract.max_duration",)),
    (PERIOD, "Place of Performance", ("contract.place_of_performance",)),
    (KEY_ADMIN, "Administered By", ("contract.administered_by",)),
    (KEY_ADMIN, "Payment Office", ("contract.payment_office",)),
    (KEY_ADMIN, "Invoice Address", ("contract.invoice_address",)),
    (KEY_ADMIN, "Accounting Data", ("contract.accounting_data",)),
    (KEY_ADMIN, "Information Contact", ("contract.information_contact_name",)),
    (KEY_ADMIN, "Contact Telephone", ("contract.information_contact_telephone",)),
    (KEY_ADMIN, "Contact Email", ("contract.information_contact_email",)),
)

# V3 Contract Summary columns, used when the forms gave no such field.
_V3_SUMMARY = {
    "contract.contract_number": "contract_number",
    "contract.solicitation_number": "solicitation_rfp",
    "contract.contract_vehicle": "contract_vehicle",
    "contract.agency_office": "agency_office",
    "contract.contractor": "contractor",
    "contract.award_date": "award_date",
    "contract.ceiling_max_aggregate": "ceiling_max_aggregate",
    "contract.minimum_guarantee": "minimum_guarantee",
    "contract.base_period": "base_period",
    "contract.options": "options",
    "contract.max_duration": "max_duration",
    "contract.task_order_range": "task_order_range",
    "contract.naics": "naics",
    "contract.size_standard": "size_standard",
}


def contract_overview_records(
    document: Document, records: dict[str, list[RawRecord]], data: list[RawRecord], subtype: str = DOD
) -> list[RawRecord]:
    details: dict[str, RawRecord] = {}
    for record in records.get("contract_details", []):
        details.setdefault(record.values.get("field_id") or "", record)
    summary = next(iter(records.get("contract_summary", [])), None)

    rows: list[RawRecord] = []

    def add(group: str, label: str, value: object, provenance: CellProvenance | None, checks=None, status=None) -> None:
        rows.append(
            RawRecord(
                record_id=f"overview:{len(rows)}:{label}",
                values={"group": group, "label": label, "value": value},
                cell_provenance={"value": provenance} if provenance else {},
                cell_checks={"value": checks} if checks else {},
                builder_status=status,
            )
        )

    add(
        IDENTIFICATION,
        "Contract Type",
        SUBTYPE_LABELS[subtype],
        make_provenance(
            document, page=None, extraction_method="subtype",
            evidence="Identified from the form number / program named on the first pages.", source_type="system",
        ),
    )
    for group, label, field_ids in _SUMMARY_FIELDS:
        for field_id in field_ids:
            record = details.get(field_id)
            if record is not None and record.values.get("value"):
                add(group, label, record.values["value"], record.cell_provenance.get("value"), record.cell_checks.get("value"))
                break
            attr = _V3_SUMMARY.get(field_id)
            if summary is not None and attr and summary.values.get(attr):
                add(group, label, summary.values[attr], summary.cell_provenance.get(attr))
                break

    # Domains are an OASIS+ concept; elsewhere the same words are ordinary
    # text ("Environmental" in a construction contract).
    domains = sorted({d for row in data for d in str(row.values.get("domain") or "").split("; ") if d})
    if domains and subtype == OASIS:
        first = next(row for row in data if row.values.get("domain"))
        add(IDENTIFICATION, "Domains", "; ".join(domains), first.cell_provenance.get("domain"))

    def count(predicate) -> int:
        return sum(1 for row in data if predicate(row.values))

    statistics = (
        ("Pages", document.page_count),
        ("CLINs / Line Items", count(lambda v: v["section"] == CLINS)),
        ("Delivery Records", count(lambda v: v["section"] == DELIVERY)),
        ("Funding Lines", count(lambda v: v["section"] == PRICING and str(v["record_type"]).startswith("Funding"))),
        ("Contract Sections", count(lambda v: v["section"] == SECTIONS and v["record_type"] == "Section")),
        ("Attachments", count(lambda v: v["section"] == ATTACHMENTS)),
        ("FAR Clauses", count(lambda v: v["section"] == FAR_CLAUSES)),
        ("DFARS Clauses", count(lambda v: v["section"] == DFARS_CLAUSES)),
        ("Other Clauses", count(lambda v: v["section"] == OTHER_CLAUSES)),
        ("Clauses Incorporated by Reference", count(lambda v: v["record_type"] == "Clause" and v.get("incorporation_type") == "Incorporated by Reference")),
        ("Clauses in Full Text", count(lambda v: v["record_type"] == "Clause" and v.get("incorporation_type") == "Incorporated in Full Text")),
        ("Records in Contract Data", len(data)),
    )
    for label, value in statistics:
        if value in (None, 0) and label not in ("FAR Clauses", "DFARS Clauses", "CLINs / Line Items"):
            continue
        provenance = make_provenance(
            document,
            page=None,
            evidence=f"Counted from the Contract Data records of {document.original_filename}.",
            extraction_method="count",
            source_type="system",
        )
        add(STATISTICS, label, value, provenance)
    return rows
