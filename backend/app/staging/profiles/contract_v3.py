"""contract_v3@1 — the canonical V3 contract model registered as a staging
profile. Pure adapter: reads `get_normalized_v3_document` (the same
assembly the V3 CSV/XLSX exports use), never re-extracts, and leaves the V3
tables and V3 export schema untouched.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.v3_document import NormalizedV3Document, RowProvenance
from app.services.v3_reader import get_normalized_v3_document
from app.staging.models import ExportCapability
from app.staging.profile import (
    AdapterResult,
    DatasetDefinition,
    FieldDefinition,
    FieldRule,
    RawRecord,
    StagingProfile,
)
from app.staging.provenance import make_provenance

F = FieldDefinition

# (model attribute, V3 column header). The header keys the summary's
# internal per-field provenance.
_SUMMARY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("contract_number", "Contract Number"),
    ("solicitation_rfp", "Solicitation / RFP"),
    ("contract_vehicle", "Contract Vehicle"),
    ("agency_office", "Agency / Office"),
    ("contractor", "Contractor"),
    ("award_date", "Award Date"),
    ("ceiling_max_aggregate", "Ceiling / Max Aggregate"),
    ("minimum_guarantee", "Minimum Guarantee"),
    ("base_period", "Base Period"),
    ("options", "Options"),
    ("max_duration", "Max Duration"),
    ("task_order_range", "Task Order Range"),
    ("naics", "NAICS"),
    ("size_standard", "Size Standard"),
)

CONTRACT_SUMMARY = DatasetDefinition(
    dataset_id="contract_summary",
    display_name="Contract Summary",
    cardinality="single",
    description="One row per contract: identification, parties, dates, financial terms.",
    identity_fields=("contract.contract_number",),
    fields=(
        F("contract.contract_number", "contract_number", "Contract Number", "code", expected=True),
        F("contract.solicitation_number", "solicitation_rfp", "Solicitation / RFP", "code", expected=True),
        F("contract.contract_vehicle", "contract_vehicle", "Contract Vehicle", expected=True),
        F("contract.agency_office", "agency_office", "Agency / Office", expected=True),
        F("contract.contractor_name", "contractor", "Contractor", expected=True),
        F("contract.award_date", "award_date", "Award Date", "date", expected=True),
        F(
            "contract.ceiling_amount",
            "ceiling_max_aggregate",
            "Ceiling / Max Aggregate",
            expected=True,
            grounding="derived",
            rules=(FieldRule("evidence_mentions", terms=("ceiling", "maximum")),),
        ),
        F(
            "contract.minimum_guarantee",
            "minimum_guarantee",
            "Minimum Guarantee",
            "money",
            expected=True,
            rules=(
                FieldRule("positive_amount", message="A minimum guarantee of zero is implausible."),
                FieldRule(
                    "evidence_mentions",
                    terms=("minimum",),
                    message="Evidence does not describe a minimum guarantee.",
                ),
            ),
        ),
        F(
            "contract.base_period",
            "base_period",
            "Base Period",
            expected=True,
            grounding="derived",
            rules=(FieldRule("evidence_mentions", terms=("base period", "base")),),
        ),
        F(
            "contract.options",
            "options",
            "Options",
            expected=True,
            grounding="derived",
            rules=(FieldRule("evidence_mentions", terms=("option",)),),
        ),
        F(
            "contract.max_duration",
            "max_duration",
            "Max Duration",
            expected=True,
            grounding="derived",
            rules=(FieldRule("evidence_mentions", terms=("term", "duration", "years", "months")),),
        ),
        F("contract.task_order_range", "task_order_range", "Task Order Range", expected=True),
        F(
            "contract.naics",
            "naics",
            "NAICS",
            "code",
            expected=True,
            rules=(FieldRule("pattern", pattern=r"\d{6}", message="NAICS must be 6 digits."),),
        ),
        F("contract.size_standard", "size_standard", "Size Standard", expected=True),
    ),
)

CLINS = DatasetDefinition(
    dataset_id="clins",
    display_name="CLINs",
    cardinality="repeating",
    description="One row per CLIN / SLIN / sub-CLIN.",
    identity_fields=("contract.clin.clin", "contract.clin.description"),
    fields=(
        F("contract.clin.clin", "clin", "CLIN", "code", expected=True),
        F("contract.clin.option_base", "option_base", "Option/Base", grounding="derived"),
        F("contract.clin.description", "description", "Description"),
        F("contract.clin.pricing_type", "pricing_type", "Pricing Type", grounding="derived"),
        F("contract.clin.max_quantity", "max_quantity", "Max Quantity"),
        F("contract.clin.unit", "unit", "Unit"),
        F("contract.clin.unit_price", "unit_price", "Unit Price", "money"),
        F("contract.clin.max_amount", "max_amount", "Max Amount", "money"),
        F("contract.clin.status", "status", "Status", grounding="derived"),
        F("contract.clin.fob", "fob", "FOB", grounding="derived"),
        F("contract.clin.purchase_request", "purchase_request", "Purchase Request", grounding="derived"),
        F("contract.clin.psc", "psc", "PSC", "code", grounding="derived"),
        F("contract.clin.pop_start", "pop_start", "POP Start", grounding="derived"),
        F("contract.clin.pop_end", "pop_end", "POP End", grounding="derived"),
        F("contract.clin.ship_to", "ship_to", "Ship To", grounding="derived"),
        F("contract.clin.dodaac", "dodaac", "DODAAC", "code", grounding="derived"),
    ),
)

FUNDING = DatasetDefinition(
    dataset_id="funding",
    display_name="Funding",
    cardinality="repeating",
    description="One row per funding line / obligation / funding requirement.",
    identity_fields=("contract.funding.funding_level", "contract.funding.funding_status"),
    fields=(
        F("contract.funding.funding_level", "funding_level", "Funding Level", grounding="derived"),
        F("contract.funding.clin", "clin", "CLIN", "code"),
        F("contract.funding.funding_status", "funding_status", "Funding Status", grounding="derived"),
        F("contract.funding.amount", "amount", "Amount", "money"),
        F(
            "contract.funding.accounting_appropriation",
            "accounting_appropriation",
            "Accounting / Appropriation",
            grounding="derived",
        ),
        F("contract.funding.purchase_request", "purchase_request", "Purchase Request", grounding="derived"),
    ),
)

PERFORMANCE_DELIVERY = DatasetDefinition(
    dataset_id="performance_delivery",
    display_name="Performance & Delivery",
    cardinality="repeating",
    identity_fields=("contract.performance.record_type", "contract.performance.requirement"),
    fields=(
        F("contract.performance.record_type", "record_type", "Record Type", grounding="derived"),
        F("contract.performance.clin", "clin", "CLIN", "code", grounding="derived"),
        F("contract.performance.start", "start", "Start", grounding="derived"),
        F("contract.performance.end_timing", "end_timing", "End / Timing", grounding="derived"),
        F(
            "contract.performance.location_destination",
            "location_destination",
            "Location / Destination",
            grounding="derived",
        ),
        F("contract.performance.requirement", "requirement", "Requirement", grounding="derived"),
    ),
)

ATTACHMENTS = DatasetDefinition(
    dataset_id="attachments",
    display_name="Attachments",
    cardinality="repeating",
    identity_fields=("contract.attachment.reference", "contract.attachment.title"),
    fields=(
        F("contract.attachment.reference", "attachment_reference", "Attachment / Reference", "code", expected=True),
        F("contract.attachment.title", "title_description", "Title / Description"),
        F(
            "contract.attachment.included_in_portfolio",
            "included_in_portfolio",
            "Included in Portfolio?",
            grounding="derived",
        ),
    ),
)


def _clause_fields(prefix: str) -> tuple[FieldDefinition, ...]:
    return (
        F(f"{prefix}.regulation", "regulation", "Regulation", grounding="derived"),
        F(f"{prefix}.clause_number", "clause_number", "Clause Number", "code", expected=True),
        # Titles/dates are enriched from the FAR Master reference, not
        # read from the contract text.
        F(f"{prefix}.clause_title", "clause_title", "Clause Title", grounding="derived"),
        F(f"{prefix}.alternate_deviation", "alternate_deviation", "Alternate / Deviation", grounding="derived"),
        F(f"{prefix}.effective_date", "effective_date", "Effective Date", grounding="derived"),
        F(f"{prefix}.incorporation_type", "incorporation_type", "Incorporation Type", grounding="derived"),
    )


CLAUSES = DatasetDefinition(
    dataset_id="clauses",
    display_name="Clauses",
    cardinality="repeating",
    description="Clauses incorporated into the contract (FAR and GSAR).",
    identity_fields=("contract.clause.clause_number", "contract.clause.clause_title"),
    fields=_clause_fields("contract.clause"),
)

FAR_REFERENCES = DatasetDefinition(
    dataset_id="far_references",
    display_name="FAR References",
    cardinality="repeating",
    description="Incidental FAR mentions — not incorporated clauses.",
    identity_fields=("contract.far_reference.reference", "contract.far_reference.subject_context"),
    fields=(
        F("contract.far_reference.reference", "far_reference", "FAR Reference", "code", grounding="derived"),
        F("contract.far_reference.reference_type", "reference_type", "Reference Type", grounding="derived"),
        F("contract.far_reference.subject_context", "subject_context", "Subject / Context", grounding="derived"),
        F("contract.far_reference.contract_clause", "contract_clause", "Contract Clause?", grounding="derived"),
    ),
)

DFARS = DatasetDefinition(
    dataset_id="dfars",
    display_name="DFARS",
    cardinality="repeating",
    identity_fields=("contract.dfars.clause_number", "contract.dfars.clause_title"),
    fields=_clause_fields("contract.dfars"),
)

ALL_FIELDS = DatasetDefinition(
    dataset_id="all_fields",
    display_name="All Fields",
    cardinality="repeating",
    description="Other accepted, source-supported label/value fields.",
    identity_fields=("contract.field.name", "contract.field.value"),
    fields=(
        F("contract.field.category", "category", "Category", grounding="none"),
        F("contract.field.name", "normalized_field", "Field", grounding="derived"),
        F("contract.field.value", "value", "Value", expected=True),
        F("contract.field.extraction_method", "extraction_method", "Extraction Method", grounding="none"),
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
        F("source.pages", "pages", "Pages", "integer", grounding="none"),
        F("source.extraction_status", "extraction_status", "Extraction Status", grounding="none"),
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

# V3 QA Review rows name the dataset they summarize by its sheet name.
_QA_CHECK_TO_DATASET = {
    "Contract Summary": "contract_summary",
    "CLINs": "clins",
    "Funding": "funding",
    "Performance / Delivery": "performance_delivery",
    "Attachments": "attachments",
    "Clauses": "clauses",
    "FAR References": "far_references",
    "DFARS": "dfars",
    "All Fields": "all_fields",
}


def _row_record(
    document: Document,
    kind: str,
    index: int,
    row,
    *,
    anchor: str | None = None,
) -> RawRecord:
    row_provenance: RowProvenance | None = getattr(row, "row_provenance", None)
    region_id = row_provenance.row_id if row_provenance else f"{kind}:{index}"
    return RawRecord(
        record_id=region_id,
        values=row.model_dump(),
        provenance=make_provenance(
            document,
            page=row.source_page,
            evidence=row.evidence,
            bbox=row_provenance.bbox if row_provenance else None,
            extraction_method=(row_provenance.extraction_method if row_provenance else None)
            or getattr(row, "extraction_method", None),
            region_id=region_id,
            anchor=anchor,
        ),
        builder_status=row.qa_status,
    )


def _summary_record(document: Document, doc: NormalizedV3Document) -> list[RawRecord]:
    summary = doc.contract_summary
    if summary is None:
        return []
    cell_provenance = {}
    for attr, header in _SUMMARY_COLUMNS:
        field_prov = summary.field_provenance.get(header)
        if not field_prov:
            continue
        cell_provenance[attr] = make_provenance(
            document,
            page=field_prov.get("page"),
            evidence=field_prov.get("evidence"),
            bbox=field_prov.get("bbox"),
            extraction_method=field_prov.get("extraction_method"),
            region_id=f"contract_summary:{attr}",
        )
    # The V3 row-level QA verdict is about completeness (how many of the
    # 14 columns were found), not about any one value — so it is NOT
    # applied to cells; each cell is judged on its own provenance.
    return [
        RawRecord(
            record_id="contract_summary",
            values=summary.model_dump(),
            cell_provenance=cell_provenance,
        )
    ]


def adapt_contract_v3(database: Session, document: Document) -> AdapterResult:
    doc = get_normalized_v3_document(database, document.id)

    records: dict[str, list[RawRecord]] = {
        "contract_summary": _summary_record(document, doc),
        "clins": [
            _row_record(document, "clin", i, row, anchor=row.clin or None)
            for i, row in enumerate(doc.clins)
        ],
        "funding": [
            _row_record(document, "funding", i, row, anchor=row.clin or None)
            for i, row in enumerate(doc.funding)
        ],
        "performance_delivery": [
            _row_record(document, "performance", i, row)
            for i, row in enumerate(doc.performance_delivery)
        ],
        "attachments": [
            _row_record(document, "attachment", i, row, anchor=row.attachment_reference or None)
            for i, row in enumerate(doc.attachments)
        ],
        "clauses": [
            _row_record(document, "clause", i, row, anchor=row.clause_number or None)
            for i, row in enumerate(doc.clauses)
        ],
        "far_references": [
            _row_record(document, "far_reference", i, row) for i, row in enumerate(doc.far_references)
        ],
        "dfars": [
            _row_record(document, "dfars", i, row, anchor=row.clause_number or None)
            for i, row in enumerate(doc.dfars)
        ],
        "all_fields": [
            _row_record(document, "field", i, row) for i, row in enumerate(doc.all_fields)
        ],
        "source_documents": [
            RawRecord(record_id=f"source:{i}", values=row.model_dump())
            for i, row in enumerate(doc.source_documents)
        ],
        "qa_review": [
            RawRecord(
                record_id=f"qa:{i}",
                values=row.model_dump(),
                links_to_dataset=_QA_CHECK_TO_DATASET.get(row.qa_check),
            )
            for i, row in enumerate(doc.qa_review)
        ],
    }
    return AdapterResult(records=records, outcome_provenance=document.ingestion_provenance)


CONTRACT_V3_PROFILE = StagingProfile(
    profile_id="contract_v3",
    profile_version=1,
    display_name="Contract",
    description=(
        "Federal contract / solicitation / award staging schema, based on the "
        "V3 canonical extraction workbook."
    ),
    document_families=("government_contract",),
    datasets=(
        CONTRACT_SUMMARY,
        CLINS,
        FUNDING,
        PERFORMANCE_DELIVERY,
        ATTACHMENTS,
        CLAUSES,
        FAR_REFERENCES,
        DFARS,
        ALL_FIELDS,
        SOURCE_DOCUMENTS,
        QA_REVIEW,
    ),
    adapter=adapt_contract_v3,
    export_capabilities=(
        ExportCapability(
            capability_id="professional_excel",
            label="Professional Excel (V3 workbook)",
            format="xlsx",
            href="/api/documents/{document_id}/v3/export.xlsx",
        ),
        *(
            ExportCapability(
                capability_id="dataset_csv",
                label=f"{name} CSV",
                format="csv",
                href=f"/api/documents/{{document_id}}/v3/{csv_name}.csv",
                dataset_id=dataset_id,
            )
            for dataset_id, csv_name, name in (
                ("all_fields", "all-fields", "All Fields"),
                ("clins", "clins", "CLINs"),
                ("funding", "funding", "Funding"),
                ("performance_delivery", "performance-delivery", "Performance & Delivery"),
                ("attachments", "attachments", "Attachments"),
                ("clauses", "clauses", "Clauses"),
                ("far_references", "far-references", "FAR References"),
                ("dfars", "dfars", "DFARS"),
                ("contract_summary", "contract-summary", "Contract Summary"),
            )
        ),
    ),
    oracle_mapping_capability="planned",
)
