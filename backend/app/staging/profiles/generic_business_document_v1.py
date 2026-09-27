"""generic_business_document@1 (superseded by @2, kept so documents pinned
to @1 keep rendering exactly as produced) — conservative fallback for any document no
specific profile is registered for (invoices until invoice@1 exists,
purchase orders, statements, unknown business documents).

Deliberately conservative: it reuses only data the canonical pipeline has
ALREADY accepted — V3 accepted label/value fields (structure-classified,
TOC/heading/narrative excluded), V3-parsed line rows, and page tables that
pass the table-quality gate. It never revives raw kv_* discovery output,
and unknown narrative/structural text never becomes a field.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.services.table_quality import filter_accepted_tables
from app.services.v3_reader import get_normalized_v3_document
from app.staging.models import ExportCapability
from app.staging.profile import (
    AdapterResult,
    DatasetDefinition,
    FieldDefinition,
    RawRecord,
    StagingProfile,
)
from app.staging.provenance import make_provenance, source_type_of, system_provenance

F = FieldDefinition

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_CONTACT_LABEL_RE = re.compile(
    r"\b(e-?mail|phone|telephone|tel\.?|fax|contact|attn|attention|point of contact|poc)\b",
    re.IGNORECASE,
)

DOCUMENT_SUMMARY = DatasetDefinition(
    dataset_id="document_summary",
    display_name="Document Summary",
    cardinality="single",
    description="What this document is and how it was processed.",
    fields=(
        F("document.document_type", "document_type", "Document Type", grounding="system", expected=True),
        F("document.source_filename", "source_filename", "Source File", grounding="system", expected=True),
        F("document.source_type", "source_type", "File Type", grounding="system", expected=True),
        F("document.page_count", "page_count", "Pages", "integer", grounding="system", expected=True),
        F("document.processing_status", "processing_status", "Processing Status", grounding="system"),
    ),
)

_FIELD_COLUMNS = (
    F("document.field.name", "name", "Field", grounding="derived"),
    F("document.field.value", "value", "Value", expected=True),
    F("document.field.extraction_method", "extraction_method", "Extraction Method", grounding="none"),
)

KEY_FIELDS = DatasetDefinition(
    dataset_id="key_fields",
    display_name="Key Fields",
    cardinality="repeating",
    description="Accepted, source-supported label/value fields.",
    identity_fields=("document.field.name", "document.field.value"),
    fields=_FIELD_COLUMNS,
)

CONTACTS = DatasetDefinition(
    dataset_id="contacts",
    display_name="Contacts",
    cardinality="repeating",
    description="Accepted fields that identify a person or contact channel.",
    identity_fields=("document.contact.label", "document.contact.value"),
    fields=(
        F("document.contact.label", "name", "Contact Field", grounding="derived"),
        F("document.contact.value", "value", "Value", expected=True),
    ),
)

LINE_ITEMS = DatasetDefinition(
    dataset_id="line_items",
    display_name="Line Items",
    cardinality="repeating",
    description="Repeating item rows: one row per line.",
    identity_fields=("document.line_item.item_number", "document.line_item.description"),
    fields=(
        F("document.line_item.item_number", "item_number", "Item", "code", expected=True),
        F("document.line_item.description", "description", "Description"),
        F("document.line_item.quantity", "quantity", "Quantity"),
        F("document.line_item.unit", "unit", "Unit"),
        F("document.line_item.unit_price", "unit_price", "Unit Price", "money"),
        F("document.line_item.amount", "amount", "Amount", "money"),
    ),
)

OTHER_TABLES = DatasetDefinition(
    dataset_id="other_tables",
    display_name="Other Tables",
    cardinality="repeating",
    description="Tables that passed the table-quality gate, not mapped to another dataset.",
    identity_fields=("document.table.columns",),
    fields=(
        F("document.table.columns", "columns", "Columns", grounding="derived", expected=True),
        F("document.table.column_count", "column_count", "Column Count", "integer", grounding="system"),
        F("document.table.row_count", "row_count", "Row Count", "integer", grounding="system"),
    ),
)

ALL_FIELDS = DatasetDefinition(
    dataset_id="all_fields",
    display_name="All Fields",
    cardinality="repeating",
    description="Every accepted field (key fields and contacts).",
    identity_fields=("document.field.name", "document.field.value"),
    fields=(
        F("document.field.category", "category", "Category", grounding="none"),
        *_FIELD_COLUMNS,
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


def _is_contact(label: str, value: str) -> bool:
    return bool(
        _CONTACT_LABEL_RE.search(label or "")
        or _EMAIL_RE.search(value or "")
        or _PHONE_RE.fullmatch((value or "").strip())
    )


def _other_tables(document: Document, pages: list[DocumentPage]) -> list[RawRecord]:
    records: list[RawRecord] = []
    for page in pages:
        tables = [
            {**table, "page_text": page.final_text or ""}
            for table in (page.tables_json or [])
            if isinstance(table, dict)
        ]
        for index, table in enumerate(filter_accepted_tables(tables)):
            headers = [str(h) for h in table.get("headers") or [] if str(h).strip()]
            if not headers:
                continue
            header_text = " | ".join(headers)
            region_id = f"table:{page.page_number}:{table.get('table_id') or index}"
            records.append(
                RawRecord(
                    record_id=region_id,
                    values={
                        "columns": header_text,
                        "column_count": len(headers),
                        "row_count": len(table.get("rows") or []),
                    },
                    provenance=make_provenance(
                        document,
                        page=page.page_number,
                        evidence=header_text,
                        extraction_method="table",
                        region_id=region_id,
                        anchor=headers[0],
                    ),
                )
            )
    return records


def adapt_generic(database: Session, document: Document) -> AdapterResult:
    doc = get_normalized_v3_document(database, document.id)
    pages = list(
        database.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        )
    )
    staging_record = database.scalars(
        select(DocumentStagingWorkbook).where(DocumentStagingWorkbook.document_id == document.id)
    ).first()

    key_fields: list[RawRecord] = []
    contacts: list[RawRecord] = []
    all_fields: list[RawRecord] = []
    for index, row in enumerate(doc.all_fields):
        region_id = row.row_provenance.row_id if row.row_provenance else f"field:{index}"
        provenance = make_provenance(
            document,
            page=row.source_page,
            evidence=row.evidence,
            bbox=row.row_provenance.bbox if row.row_provenance else None,
            extraction_method=row.extraction_method,
            region_id=region_id,
        )
        contact = _is_contact(row.normalized_field, row.value)
        values = {
            "name": row.normalized_field,
            "value": row.value,
            "extraction_method": row.extraction_method,
            "category": "Contact" if contact else "Key Field",
        }
        record = RawRecord(
            record_id=region_id, values=values, provenance=provenance, builder_status=row.qa_status
        )
        (contacts if contact else key_fields).append(record)
        all_fields.append(record)

    line_items = []
    for index, row in enumerate(doc.clins):
        region_id = row.row_provenance.row_id if row.row_provenance else f"line:{index}"
        line_items.append(
            RawRecord(
                record_id=region_id,
                values={
                    "item_number": row.clin,
                    "description": row.description,
                    "quantity": row.max_quantity,
                    "unit": row.unit,
                    "unit_price": row.unit_price,
                    "amount": row.max_amount,
                },
                provenance=make_provenance(
                    document,
                    page=row.source_page,
                    evidence=row.evidence,
                    bbox=row.row_provenance.bbox if row.row_provenance else None,
                    extraction_method="table",
                    region_id=region_id,
                    anchor=row.clin or None,
                ),
                builder_status=row.qa_status,
            )
        )

    summary = RawRecord(
        record_id="document_summary",
        values={
            "document_type": (
                staging_record.document_family_label if staging_record else None
            )
            or "Unclassified business document",
            "source_filename": document.original_filename,
            "source_type": source_type_of(document).upper(),
            "page_count": document.page_count,
            "processing_status": document.processing_status,
        },
        provenance=system_provenance(document),
    )

    return AdapterResult(
        records={
            "document_summary": [summary],
            "key_fields": key_fields,
            "contacts": contacts,
            "line_items": line_items,
            "other_tables": _other_tables(document, pages),
            "all_fields": all_fields,
            "source_documents": [
                RawRecord(record_id=f"source:{i}", values=row.model_dump())
                for i, row in enumerate(doc.source_documents)
            ],
        },
        outcome_provenance=document.ingestion_provenance,
    )


GENERIC_PROFILE_V1 = StagingProfile(
    profile_id="generic_business_document",
    profile_version=1,
    display_name="Generic Business Document",
    description=(
        "Conservative fallback for business documents without a dedicated "
        "profile: accepted fields, contacts, line items and quality-gated tables."
    ),
    document_families=("unknown", "generic_business"),
    datasets=(
        DOCUMENT_SUMMARY,
        KEY_FIELDS,
        CONTACTS,
        LINE_ITEMS,
        OTHER_TABLES,
        ALL_FIELDS,
        SOURCE_DOCUMENTS,
        QA_REVIEW,
    ),
    adapter=adapt_generic,
    export_capabilities=(
        ExportCapability(
            capability_id="professional_excel",
            label="Professional Excel (staging workbook)",
            format="xlsx",
            href="/api/documents/{document_id}/staging-workbook/export.xlsx",
        ),
        *(
            ExportCapability(
                capability_id="dataset_csv",
                label=f"{definition.display_name} CSV",
                format="csv",
                href=f"/api/documents/{{document_id}}/staging-workbook/datasets/{definition.dataset_id}.csv",
                dataset_id=definition.dataset_id,
            )
            for definition in (DOCUMENT_SUMMARY, KEY_FIELDS, CONTACTS, LINE_ITEMS, OTHER_TABLES, ALL_FIELDS)
        ),
    ),
    oracle_mapping_capability="none",
    auto_qa_dataset="qa_review",
)
