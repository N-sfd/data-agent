"""generic_business_document@2 — fallback profile for any document no
specific profile is registered for.

It INTERPRETS the schema-neutral structure (app/source_structure/): it
never looks for particular business fields. Accepted label/value
candidates become Key Fields (or Contacts when the value is a contact
channel), accepted tables with repeating, amount-bearing rows become Line
Items, other accepted tables become Other Tables. Rejected/ambiguous
structure is summarized in QA Review; narrative never becomes a field.

@2 replaced @1's V3-only inputs with structural candidates (@1 remains
registered for documents pinned to it).
"""

from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.services.v3_reader import get_normalized_v3_document
from app.source_structure.models import FieldCandidate, TableCandidate, TableCell
from app.source_structure.ocr_geometry import PageGeometry
from app.source_structure.service import get_or_build_source_structure
from app.source_structure.text_shapes import normalize_space
from app.staging.models import CellProvenance, ExportCapability
from app.staging.profile import (
    AdapterResult,
    DatasetDefinition,
    FieldDefinition,
    RawRecord,
    StagingProfile,
)
from app.staging.provenance import make_provenance, source_type_of, system_provenance

F = FieldDefinition

_CONTACT_TYPES = {"email", "phone"}
_CONTACT_LABEL = re.compile(
    r"\b(e-?mail|phone|telephone|tel|fax|mobile|cell|contact|attn|attention)\b", re.I
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
        F("document.page_count", "page_count", "Pages", "integer", grounding="system"),
        F("document.processing_status", "processing_status", "Processing Status", grounding="system"),
        F("document.structure_summary", "structure_summary", "Structure Found", grounding="system"),
    ),
)

_FIELD_COLUMNS = (
    F("document.field.name", "name", "Field", grounding="derived"),
    F("document.field.value", "value", "Value", expected=True),
    F("document.field.value_type", "value_type", "Type", grounding="none"),
    F("document.field.extraction_method", "extraction_method", "Found By", grounding="none"),
)

KEY_FIELDS = DatasetDefinition(
    dataset_id="key_fields",
    display_name="Key Fields",
    cardinality="repeating",
    description="Label/value pairs found in the document's structure.",
    identity_fields=("document.field.name", "document.field.value"),
    fields=_FIELD_COLUMNS,
)

CONTACTS = DatasetDefinition(
    dataset_id="contacts",
    display_name="Contacts",
    cardinality="repeating",
    description="Contact channels and contact/address blocks.",
    identity_fields=("document.contact.label", "document.contact.value"),
    fields=(
        F("document.contact.label", "name", "Contact Field", grounding="derived"),
        F("document.contact.value", "value", "Value", expected=True),
        F("document.contact.value_type", "value_type", "Type", grounding="none"),
    ),
)

LINE_ITEMS = DatasetDefinition(
    dataset_id="line_items",
    display_name="Line Items",
    cardinality="repeating",
    description=(
        "Rows of accepted tables whose structure is repeating records with "
        "amount columns. Columns are mapped from structural roles, not header names."
    ),
    identity_fields=("document.line_item.item_number", "document.line_item.description"),
    fields=(
        F("document.line_item.item_number", "item_number", "Item"),
        F("document.line_item.description", "description", "Description"),
        F("document.line_item.quantity", "quantity", "Quantity", "number"),
        F("document.line_item.unit", "unit", "Unit"),
        F("document.line_item.unit_price", "unit_price", "Unit Price", "money"),
        F("document.line_item.amount", "amount", "Amount", "money"),
        F("document.line_item.other_values", "other_values", "Other Columns", grounding="derived"),
        F("document.line_item.source_table", "source_table", "Table", grounding="none"),
    ),
)

OTHER_TABLES = DatasetDefinition(
    dataset_id="other_tables",
    display_name="Other Tables",
    cardinality="repeating",
    description="Accepted tables that are not repeating amount-bearing records.",
    identity_fields=("document.table.columns",),
    fields=(
        F("document.table.columns", "columns", "Columns", grounding="derived", expected=True),
        F("document.table.column_count", "column_count", "Column Count", "integer", grounding="system"),
        F("document.table.row_count", "row_count", "Row Count", "integer", grounding="system"),
        F("document.table.first_row", "first_row", "First Row", grounding="derived"),
        F("document.table.detection", "detection", "Detected By", grounding="none"),
    ),
)

ALL_FIELDS = DatasetDefinition(
    dataset_id="all_fields",
    display_name="All Fields",
    cardinality="repeating",
    description="Every accepted scalar candidate (key fields and contacts).",
    identity_fields=("document.field.name", "document.field.value"),
    fields=(F("document.field.category", "category", "Category", grounding="none"), *_FIELD_COLUMNS),
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


def _field_provenance(document: Document, candidate: FieldCandidate) -> CellProvenance:
    single_line = "\n" not in candidate.raw_value.strip()
    provenance = make_provenance(
        document,
        page=candidate.page,
        evidence=candidate.evidence_text,
        bbox=candidate.value_bbox,
        extraction_method=f"{candidate.extraction_method}:{candidate.structural_relation}",
        region_id=candidate.source_region_ids[0] if candidate.source_region_ids else candidate.candidate_id,
        anchor=candidate.raw_label.strip(),
        locator=candidate.source_locator,
        source_type="html" if candidate.extraction_method == "dom" else None,
    )
    # A multi-line value (an address block) is highlighted as its region.
    provenance.highlight_text = candidate.raw_value.strip() if single_line else None
    return provenance


def _cell_provenance(
    document: Document, table: TableCandidate, row: list[TableCell], cell: TableCell, anchor: str | None
) -> CellProvenance:
    row_text = " | ".join(c.text for c in row if c.text)
    provenance = make_provenance(
        document,
        page=table.page,
        evidence=row_text,
        bbox=cell.bbox,
        extraction_method=f"{table.extraction_method}:{table.detection_method}",
        region_id=cell.region_id,
        anchor=anchor,
        locator=cell.source_locator,
        source_type="html" if table.extraction_method == "dom" else None,
    )
    provenance.highlight_text = cell.text or None
    return provenance


def _is_line_item_table(table: TableCandidate) -> bool:
    hints = {h for hs in table.column_hints.values() for h in hs}
    return (
        table.acceptance == "accepted"
        and "repeating_records" in table.table_hints
        and "numeric_amount_column" in hints
        and bool(hints & {"description_column", "identifier_column"})
    )


def _columns_with(table: TableCandidate, hint: str) -> list[int]:
    return sorted(c for c, hs in table.column_hints.items() if hint in hs)


def _line_item_records(
    document: Document, table: TableCandidate, table_label: str
) -> tuple[list[RawRecord], list[RawRecord]]:
    """(line records, total-row key-field records)."""

    identifier = next(iter(_columns_with(table, "identifier_column")), None)
    description = next(iter(_columns_with(table, "description_column")), None)
    quantity = next(iter(_columns_with(table, "quantity_column")), None)
    unit = next(iter(_columns_with(table, "unit_column")), None)
    amounts = _columns_with(table, "numeric_amount_column")
    amount = amounts[-1] if amounts else None
    unit_price = amounts[-2] if len(amounts) >= 2 else None
    mapped = {c for c in (identifier, description, quantity, unit, amount, unit_price) if c is not None}

    lines: list[RawRecord] = []
    totals: list[RawRecord] = []
    for r, row in enumerate(table.rows):
        by_column = {cell.column_index: cell for cell in row}
        anchor_cell = by_column.get(identifier) if identifier is not None else None
        anchor = (anchor_cell.text if anchor_cell and anchor_cell.text else None) or next(
            (c.text for c in row if c.text), None
        )

        if r in table.total_row_indices:
            filled = [c for c in row if c.text]
            if len(filled) >= 2:
                label_cell, value_cell = filled[0], filled[-1]
                provenance = _cell_provenance(document, table, row, value_cell, label_cell.text)
                totals.append(
                    RawRecord(
                        record_id=f"{table.candidate_id}:total:{r}",
                        values={
                            "name": label_cell.text,
                            "value": value_cell.text,
                            "value_type": "currency",
                            "extraction_method": "table total row",
                            "category": "Key Field",
                        },
                        provenance=provenance,
                    )
                )
            continue

        values: dict[str, object] = {"source_table": table_label}
        cell_provenance: dict[str, CellProvenance] = {}
        for key, column in (
            ("item_number", identifier),
            ("description", description),
            ("quantity", quantity),
            ("unit", unit),
            ("unit_price", unit_price),
            ("amount", amount),
        ):
            cell = by_column.get(column) if column is not None else None
            if cell is None or not cell.text:
                continue
            values[key] = cell.text
            cell_provenance[key] = _cell_provenance(document, table, row, cell, anchor)
        other = [
            f"{table.headers[c] if c < len(table.headers) else f'Column {c + 1}'}: {cell.text}"
            for c, cell in sorted(by_column.items())
            if c not in mapped and cell.text
        ]
        if other:
            values["other_values"] = "; ".join(other)
        if len(values) <= 1:
            continue
        lines.append(
            RawRecord(
                record_id=f"{table.candidate_id}:row:{r}",
                values=values,
                provenance=_cell_provenance(document, table, row, row[0], anchor),
                cell_provenance=cell_provenance,
            )
        )
    return lines, totals


def _table_label(table: TableCandidate, index: int) -> str:
    where = f"page {table.page}" if table.page else (
        f"HTML table {table.source_locator.table_index + 1}"
        if table.source_locator and table.source_locator.table_index is not None
        else "table"
    )
    return f"Table {index} ({where})"


def adapt_generic(database: Session, document: Document) -> AdapterResult:
    structure = get_or_build_source_structure(database, document)
    staging_record = database.scalars(
        select(DocumentStagingWorkbook).where(DocumentStagingWorkbook.document_id == document.id)
    ).first()

    key_fields: list[RawRecord] = []
    contacts: list[RawRecord] = []
    seen: set[tuple[str, str]] = set()

    for candidate in structure.field_candidates:
        if candidate.acceptance != "accepted":
            continue
        signature = (candidate.label_text.lower(), normalize_space(candidate.raw_value).lower())
        if signature in seen:
            continue
        seen.add(signature)
        is_contact = candidate.value_type_hint in _CONTACT_TYPES or bool(
            _CONTACT_LABEL.search(candidate.label_text)
        )
        record = RawRecord(
            record_id=candidate.candidate_id,
            values={
                "name": candidate.label_text,
                "value": candidate.raw_value.strip(),
                "value_type": candidate.value_type_hint,
                "extraction_method": candidate.structural_relation.replace("_", " "),
                "category": "Contact" if is_contact else "Key Field",
            },
            provenance=_field_provenance(document, candidate),
        )
        (contacts if is_contact else key_fields).append(record)

    # Fields the canonical V3 classifier accepted (e.g. numbered government
    # form labels) that the structural pass didn't already produce.
    try:
        v3 = get_normalized_v3_document(database, document.id)
    except ValueError:
        v3 = None
    geometry = PageGeometry(database, document.id)
    for index, row in enumerate(v3.all_fields if v3 else []):
        signature = (row.normalized_field.lower(), normalize_space(row.value).lower())
        if signature in seen:
            continue
        seen.add(signature)
        key_fields.append(
            RawRecord(
                record_id=row.row_provenance.row_id if row.row_provenance else f"v3field:{index}",
                values={
                    "name": row.normalized_field,
                    "value": row.value,
                    "value_type": None,
                    "extraction_method": f"v3 {row.extraction_method}",
                    "category": "Key Field",
                },
                provenance=make_provenance(
                    document,
                    page=row.source_page,
                    evidence=row.evidence,
                    bbox=geometry.pdf_bbox(
                        row.source_page, row.row_provenance.bbox, row.row_provenance.bbox_space
                    )
                    if row.row_provenance
                    else None,
                    extraction_method=row.extraction_method,
                    region_id=row.row_provenance.row_id if row.row_provenance else None,
                ),
                builder_status=row.qa_status,
            )
        )

    for region in structure.regions:
        if region.region_type != "CONTACT_BLOCK":
            continue
        contacts.append(
            RawRecord(
                record_id=region.region_id,
                values={"name": "Contact block", "value": region.text, "value_type": "address"},
                provenance=make_provenance(
                    document,
                    page=region.page,
                    evidence=region.text,
                    bbox=region.bbox,
                    extraction_method=f"{region.extraction_method}:contact_block",
                    region_id=region.region_id,
                    anchor=region.text.splitlines()[0] if region.text else None,
                    locator=region.source_locator,
                    source_type="html" if region.extraction_method == "dom" else None,
                ),
            )
        )

    line_items: list[RawRecord] = []
    other_tables: list[RawRecord] = []
    accepted_tables = [t for t in structure.table_candidates if t.acceptance == "accepted"]
    for index, table in enumerate(accepted_tables, start=1):
        label = _table_label(table, index)
        if _is_line_item_table(table):
            lines, totals = _line_item_records(document, table, label)
            line_items.extend(lines)
            key_fields.extend(totals)
            continue
        header_text = " | ".join(h for h in table.headers if h)
        first_row = " | ".join(c.text for c in table.rows[0] if c.text) if table.rows else ""
        other_tables.append(
            RawRecord(
                record_id=table.candidate_id,
                values={
                    "columns": header_text,
                    "column_count": len(table.headers),
                    "row_count": len(table.rows),
                    "first_row": first_row or None,
                    "detection": table.detection_method.replace("_", " "),
                },
                provenance=make_provenance(
                    document,
                    page=table.page,
                    evidence=f"{header_text}\n{first_row}".strip(),
                    bbox=table.bbox,
                    extraction_method=f"{table.extraction_method}:{table.detection_method}",
                    region_id=table.region_id,
                    anchor=next((h for h in table.headers if h), None),
                    locator=table.source_locator,
                    source_type="html" if table.extraction_method == "dom" else None,
                ),
            )
        )

    all_fields = key_fields + contacts
    stats = structure.stats
    regions = stats.regions_by_type
    summary_parts = [
        f"{stats.field_candidates.get('accepted', 0)} label/value pairs",
        f"{len(accepted_tables)} tables",
        f"{regions.get('HEADING', 0)} headings",
    ]
    rejected_fields = [f for f in structure.field_candidates if f.acceptance != "accepted"]
    rejected_tables = [t for t in structure.table_candidates if t.acceptance != "accepted"]
    narrative = regions.get("NARRATIVE", 0) + regions.get("PARAGRAPH", 0)
    reason_counts = Counter(r for f in rejected_fields for r in f.reasons)
    qa_rows = [
        RawRecord(
            record_id="qa:structure:fields",
            values={
                "qa_check": "Structure: label/value candidates",
                "result": "PASS" if not rejected_fields else "REVIEW",
                "details": (
                    f"{stats.field_candidates.get('accepted', 0)} accepted, "
                    f"{len(rejected_fields)} not accepted"
                    + (
                        " (" + ", ".join(f"{r.replace('_', ' ')}: {n}" for r, n in reason_counts.most_common(3)) + ")"
                        if reason_counts
                        else ""
                    )
                    + "."
                ),
                "action": "Rejected candidates are excluded; check the source if an expected field is absent."
                if rejected_fields
                else "None.",
            },
        ),
        RawRecord(
            record_id="qa:structure:tables",
            values={
                "qa_check": "Structure: tables",
                "result": "PASS" if not rejected_tables else "REVIEW",
                "details": f"{len(accepted_tables)} accepted, {len(rejected_tables)} rejected by the table-quality gate.",
                "action": "None." if not rejected_tables else "Rejected tables (e.g. prose laid out in columns) are excluded.",
            },
        ),
        RawRecord(
            record_id="qa:structure:narrative",
            values={
                "qa_check": "Structure: narrative",
                "result": "INFO",
                "details": f"{narrative} paragraph/narrative regions were read but not turned into fields.",
                "action": "Available in Source / Transcription.",
            },
        ),
    ]
    if structure.warnings:
        qa_rows.append(
            RawRecord(
                record_id="qa:structure:warnings",
                values={
                    "qa_check": "Structure: warnings",
                    "result": "REVIEW",
                    "details": "; ".join(structure.warnings),
                    "action": "Re-run extraction if the source file was unavailable.",
                },
            )
        )

    source_type = source_type_of(document)
    summary = RawRecord(
        record_id="document_summary",
        values={
            "document_type": (staging_record.document_family_label if staging_record else None)
            or "Unclassified business document",
            "source_filename": document.original_filename,
            "source_type": source_type.upper(),
            # HTML has no pages; don't present its single ingestion page as one.
            "page_count": None if source_type == "html" else document.page_count,
            "processing_status": document.processing_status,
            "structure_summary": ", ".join(summary_parts),
        },
        provenance=system_provenance(document),
    )

    return AdapterResult(
        records={
            "document_summary": [summary],
            "key_fields": key_fields,
            "contacts": contacts,
            "line_items": line_items,
            "other_tables": other_tables,
            "all_fields": all_fields,
            "source_documents": [
                RawRecord(record_id=f"source:{i}", values=row.model_dump())
                for i, row in enumerate(v3.source_documents if v3 else [])
            ],
            "qa_review": qa_rows,
        },
        outcome_provenance=document.ingestion_provenance,
    )


GENERIC_PROFILE = StagingProfile(
    profile_id="generic_business_document",
    profile_version=2,
    display_name="Generic Business Document",
    description=(
        "Fallback for business documents without a dedicated profile: "
        "structural label/value pairs, contacts, repeating line tables and "
        "other accepted tables."
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
