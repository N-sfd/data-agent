"""XML Document profile (xml_document@1): any well-formed XML file, staged
from its own structure.

The repeating element that carries the data becomes one record per element
(Records 1–4, captioned per file: "Clauses" for <Clause>); its child
elements and attributes become the columns, captioned from the file's own
tag names. Values outside every record are Document Details. Each value's
provenance is its element path (/Root/Clause[3]/Title). Columns are generic
slots: a file names the ones it uses (labelled_columns_only).
"""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.services.document_storage import ensure_local_copy
from app.staging.models import ExportCapability, SourceLocator
from app.staging.profile import (
    SOURCE_SHEET,
    ExportSheet,
    AdapterResult,
    DatasetDefinition,
    FieldDefinition,
    RawRecord,
    Recognition,
    StagingProfile,
)
from app.staging.provenance import make_provenance
from app.xml_records.parse import MAX_COLUMNS, MAX_GROUPS, XmlDocument, XmlSourceError, XmlValue, parse_xml

F = FieldDefinition
FAMILY = "xml_data"
_XML_SUFFIXES = {".xml"}
SLOTS = MAX_COLUMNS
_METHOD = "xml_element"


def _slot(index: int) -> str:
    return f"col_{index:03d}"


def _record_dataset(number: int) -> DatasetDefinition:
    return DatasetDefinition(
        dataset_id=f"xml_records_{number}",
        display_name=f"Records {number}",
        cardinality="repeating",
        description="One row per repeating XML element; columns are its child elements and attributes.",
        labelled_columns_only=True,
        source_adaptive_columns=True,
        fields=(
            *(F(f"xml.records_{number}.{_slot(i)}", _slot(i), f"Column {i}") for i in range(1, SLOTS + 1)),
            # The XML file each record comes from (a fact about the file).
            F(f"xml.records_{number}.source_xml", "source_xml", "Source XML", grounding="system"),
        ),
    )


RECORD_DATASETS = tuple(_record_dataset(n) for n in range(1, MAX_GROUPS + 1))

DETAILS = DatasetDefinition(
    dataset_id="key_fields",
    display_name="Document Details",
    cardinality="repeating",
    description="Values outside the repeating records (header, batch and file-level elements).",
    identity_fields=("xml.detail.label", "xml.detail.value"),
    fields=(
        F("xml.detail.label", "label", "Field", grounding="none"),
        F("xml.detail.value", "value", "Value", expected=True),
        F("xml.detail.category", "category", "Element", grounding="none"),
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


def _source_path(document: Document) -> Path:
    return ensure_local_copy(get_settings(), stored_filename=document.stored_filename)


@lru_cache(maxsize=8)
def _parse_cached(path: str, size: int, mtime: float) -> tuple[XmlDocument, int]:
    started = time.perf_counter()
    parsed = parse_xml(Path(path).read_bytes())
    return parsed, int((time.perf_counter() - started) * 1000)


def load_xml(document: Document) -> tuple[XmlDocument, int]:
    path = _source_path(document)
    stat = path.stat()
    return _parse_cached(str(path), stat.st_size, stat.st_mtime)


def recognize_xml_document(database: Session, document: Document) -> Recognition:
    if Path(document.stored_filename or "").suffix.lower() not in _XML_SUFFIXES:
        return Recognition(0.0, ["not an XML source"])
    return Recognition(1.0, ["XML source: staged from its own element structure"])


def _provenance(document: Document, value: XmlValue, section: list[str]):
    return make_provenance(
        document,
        page=None,
        evidence=value.value,
        extraction_method=_METHOD,
        locator=SourceLocator(dom_path=value.path, section_path=section),
        source_type="xml",
        anchor=value.label,
    )


def adapt_xml(database: Session, document: Document) -> AdapterResult:
    try:
        parsed, parse_ms = load_xml(document)
    except (XmlSourceError, OSError) as exc:
        return AdapterResult(
            records={
                "qa_review": [
                    RawRecord(
                        record_id="qa:parse",
                        values={
                            "qa_check": "XML parsing",
                            "result": "FAILED",
                            "details": str(exc),
                            "action": "Check that the file is well-formed XML.",
                        },
                    )
                ]
            },
            omit_datasets={d.dataset_id for d in RECORD_DATASETS},
        )

    records: dict[str, list[RawRecord]] = {}
    labels: dict[str, dict[str, str]] = {}
    names: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    qa: list[RawRecord] = []

    for number, (definition, group) in enumerate(zip(RECORD_DATASETS, parsed.groups), start=1):
        slot_of = {key: _slot(i) for i, (key, _) in enumerate(group.columns, start=1)}
        labels[definition.dataset_id] = {
            **{f"xml.records_{number}.{slot_of[key]}": label for key, label in group.columns},
            f"xml.records_{number}.source_xml": "Source XML",
        }
        names[definition.dataset_id] = group.label
        descriptions[definition.dataset_id] = (
            f"One row per <{group.tag}> element ({group.path}); columns are its child elements, "
            "captioned from the file's own tag names."
        )
        rows = []
        for index, record in enumerate(group.records, start=1):
            section = [parsed.root_tag, record.path]
            values = {slot_of[key]: value.value for key, value in record.values.items() if key in slot_of}
            values["source_xml"] = document.original_filename
            cell_provenance = {
                slot_of[key]: _provenance(document, value, section)
                for key, value in record.values.items()
                if key in slot_of
            }
            rows.append(
                RawRecord(
                    record_id=f"{definition.dataset_id}:{index}",
                    values=values,
                    cell_provenance=cell_provenance,
                )
            )
        records[definition.dataset_id] = rows
        if group.dropped_columns:
            qa.append(
                RawRecord(
                    record_id=f"qa:{definition.dataset_id}:columns",
                    values={
                        "qa_check": f"{group.label} columns",
                        "result": "REVIEW",
                        "details": f"{group.dropped_columns} value(s) beyond the first {SLOTS} columns are not staged.",
                        "action": "Use the JSON export or review the source XML for the remaining elements.",
                    },
                )
            )

    records["key_fields"] = [
        RawRecord(
            record_id=f"key_fields:{index}",
            values={"label": value.label, "value": value.value, "category": value.path.rsplit("/", 1)[0] or "/"},
            cell_provenance={"value": _provenance(document, value, [parsed.root_tag])},
        )
        for index, value in enumerate(parsed.details, start=1)
    ]
    summary = ", ".join(f"{len(g.records)} {g.label}" for g in parsed.groups) or "no repeating records"
    records["source_documents"] = [
        RawRecord(
            record_id="source:primary",
            values={
                "source_document": document.original_filename,
                "role": f"XML source (<{parsed.root_tag}>)",
                "extraction_method": "XML elements (hardened parser: no entities, DTDs or network)",
                "extraction_status": f"{parsed.element_count} elements; {summary}; {len(parsed.details)} detail value(s)",
                "processing_ms": parse_ms,
            },
        )
    ]
    records["qa_review"] = qa
    used = {d.dataset_id for d in RECORD_DATASETS[: len(parsed.groups)]}
    return AdapterResult(
        records=records,
        outcome_provenance=document.ingestion_provenance,
        column_labels=labels,
        dataset_names=names,
        dataset_descriptions=descriptions,
        omit_datasets={d.dataset_id for d in RECORD_DATASETS} - used,
    )


XML_DOCUMENT_PROFILE = StagingProfile(
    profile_id="xml_document",
    profile_version=1,
    display_name="XML Document",
    description=(
        "Any XML file staged from its own structure: one row per repeating element, columns captioned from "
        "the file's tag names, paragraph markup kept together, element paths as provenance."
    ),
    document_families=(FAMILY,),
    datasets=(*RECORD_DATASETS, DETAILS, SOURCE_DOCUMENTS, QA_REVIEW),
    adapter=adapt_xml,
    # Each record group under the name the file gives it ("Clauses").
    export_sheets=(
        *(ExportSheet(None, (definition.dataset_id,)) for definition in RECORD_DATASETS),
        ExportSheet("Document Details", ("key_fields",)),
        ExportSheet(SOURCE_SHEET, ()),
    ),
    export_capabilities=(
        ExportCapability(
            capability_id="professional_excel",
            label="XML Extraction Workbook (Excel)",
            format="xlsx",
            href="/api/documents/{document_id}/staging-workbook/export.xlsx",
        ),
        ExportCapability(
            capability_id="workbook_json",
            label="XML Extraction (JSON)",
            format="json",
            href="/api/documents/{document_id}/staging-workbook/export.json",
        ),
        *(
            ExportCapability(
                capability_id="dataset_csv",
                label=f"{definition.display_name} CSV",
                format="csv",
                href=f"/api/documents/{{document_id}}/staging-workbook/datasets/{definition.dataset_id}.csv",
                dataset_id=definition.dataset_id,
            )
            for definition in (*RECORD_DATASETS, DETAILS)
        ),
    ),
    auto_qa_dataset="qa_review",
    source_structure="none",
    document_recognizer=recognize_xml_document,
    contract_pipeline=False,
)

__all__ = ["XML_DOCUMENT_PROFILE"]
