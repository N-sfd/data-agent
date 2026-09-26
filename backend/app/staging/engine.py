"""Profile-independent workbook assembly: adapter RawRecords → validated
StagingWorkbook. No profile-specific logic lives here."""

from __future__ import annotations

import re

from app.models.document import Document
from app.services.extraction_outcome import build_outcome_from_counts
from app.staging.models import (
    MISSING,
    NEEDS_REVIEW,
    VERIFIED,
    CellProvenance,
    ExtractionOutcomeModel,
    ProcessingMetadata,
    ProfileDescriptor,
    QaSummary,
    StagingCell,
    StagingColumn,
    StagingDataset,
    StagingRecord,
    StagingWorkbook,
)
from app.staging.profile import AdapterResult, DatasetDefinition, RawRecord, StagingProfile
from app.staging.validation import NUMBER_RE, evaluate_cell, is_empty, to_number


def evidence_literal(value: object, evidence: str | None, value_type: str) -> str | None:
    """The exact substring of `evidence` that expresses `value` — what the
    source viewer should highlight. None when the value isn't literally in
    the evidence (the viewer then falls back to the record's anchor)."""

    if not evidence or is_empty(value):
        return None
    if value_type in ("money", "number", "integer") or isinstance(value, (int, float)):
        target = to_number(value)
        if target is None:
            return None
        for match in NUMBER_RE.finditer(evidence):
            try:
                if abs(float(match.group(0).replace(",", "")) - target) < 0.005:
                    return match.group(0)
            except ValueError:
                continue
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    parts = [re.escape(part) for part in text.split(" ")]
    match = re.search(r"\s+".join(parts), evidence, re.IGNORECASE)
    return match.group(0) if match else None


def _cell_provenance(
    raw: RawRecord, key: str, value: object, value_type: str
) -> CellProvenance | None:
    own = raw.cell_provenance.get(key)
    base = own or raw.provenance
    if base is None or is_empty(value):
        return base if own else None
    if base.highlight_text:
        return base
    literal = evidence_literal(value, base.evidence_text, value_type)
    return base.model_copy(update={"highlight_text": literal})


def _display_value(value: object) -> object:
    if isinstance(value, float) and value.is_integer():
        return value
    return value


def _build_dataset(definition: DatasetDefinition, raws: list[RawRecord]) -> StagingDataset:
    if definition.cardinality == "single" and definition.role == "business" and not raws:
        # A single-record dataset with nothing found still renders every
        # expected field as Missing, rather than an empty panel.
        raws = [RawRecord(record_id=f"{definition.dataset_id}:empty", values={})]

    records: list[StagingRecord] = []
    for raw in raws:
        flagged = "review" in (raw.builder_status or "").lower()
        cells: dict[str, StagingCell] = {}
        for field_def in definition.fields:
            value = raw.values.get(field_def.key)
            provenance = _cell_provenance(raw, field_def.key, value, field_def.value_type)
            validation, status, reasons = evaluate_cell(
                field_def, value, provenance, record_flagged=flagged
            )
            cells[field_def.canonical_field] = StagingCell(
                canonical_field=field_def.canonical_field,
                display_label=field_def.display_label,
                value=None if is_empty(value) else _display_value(value),
                raw_value=None if is_empty(value) else str(value),
                value_type=field_def.value_type,
                provenance=provenance if not is_empty(value) else None,
                validation=validation,
                review_status=status,
                review_reasons=reasons,
            )

        record_status = None
        if definition.role == "business":
            statuses = {cell.review_status for cell in cells.values()}
            if NEEDS_REVIEW in statuses:
                record_status = NEEDS_REVIEW
            elif VERIFIED in statuses:
                record_status = VERIFIED
            elif MISSING in statuses:
                record_status = MISSING
        records.append(
            StagingRecord(
                record_id=raw.record_id,
                cells=cells,
                record_status=record_status,
                links_to_dataset=raw.links_to_dataset,
            )
        )

    return StagingDataset(
        dataset_id=definition.dataset_id,
        display_name=definition.display_name,
        cardinality=definition.cardinality,
        role=definition.role,
        description=definition.description,
        columns=[
            StagingColumn(
                canonical_field=f.canonical_field,
                key=f.key,
                display_label=f.display_label,
                value_type=f.value_type,
                expected=f.expected,
            )
            for f in definition.fields
        ],
        records=records,
        identity_fields=list(definition.identity_fields),
    )


def _has_value(record: StagingRecord) -> bool:
    return any(cell.value is not None for cell in record.cells.values())


def _auto_qa_records(datasets: list[StagingDataset]) -> list[RawRecord]:
    """One QA row per business dataset, summarizing its validated cells —
    the same category-level checklist shape as the V3 QA Review sheet."""

    records: list[RawRecord] = []
    for dataset in datasets:
        if dataset.role != "business":
            continue
        populated = [record for record in dataset.records if _has_value(record)]
        flagged = [r for r in populated if r.record_status == NEEDS_REVIEW]
        missing = sum(
            1
            for record in dataset.records
            for cell in record.cells.values()
            if cell.review_status == MISSING
        )
        if not populated:
            result, details, action = (
                "NOT FOUND",
                "No source-supported records were identified.",
                "Confirm against the source whether this data exists.",
            )
        elif flagged or missing:
            parts = [f"{len(populated)} record(s)"]
            if flagged:
                parts.append(f"{len(flagged)} flagged Needs Review")
            if missing:
                parts.append(f"{missing} expected field(s) Missing")
            result, details, action = (
                "REVIEW",
                "; ".join(parts) + ".",
                "Review flagged values against source evidence.",
            )
        else:
            result, details, action = (
                "PASS",
                f"{len(populated)} record(s), all verified against source evidence.",
                "None.",
            )
        records.append(
            RawRecord(
                record_id=f"qa:{dataset.dataset_id}",
                values={
                    "qa_check": dataset.display_name,
                    "result": result,
                    "details": details,
                    "action": action,
                },
                links_to_dataset=dataset.dataset_id,
            )
        )
    return records


def profile_descriptor(profile: StagingProfile, document_id: str) -> ProfileDescriptor:
    return ProfileDescriptor(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        display_name=profile.display_name,
        description=profile.description,
        document_families=list(profile.document_families),
        export_capabilities=[
            capability.model_copy(
                update={"href": capability.href.replace("{document_id}", document_id)}
            )
            for capability in profile.export_capabilities
        ],
        oracle_mapping_capability=profile.oracle_mapping_capability,
    )


def assemble_workbook(
    *,
    profile: StagingProfile,
    document: Document,
    adapter_result: AdapterResult,
    metadata: ProcessingMetadata,
) -> StagingWorkbook:
    datasets = [
        _build_dataset(definition, adapter_result.records.get(definition.dataset_id, []))
        for definition in profile.datasets
    ]
    if profile.auto_qa_dataset:
        qa_definition = profile.dataset(profile.auto_qa_dataset)
        datasets = [
            _build_dataset(qa_definition, _auto_qa_records(datasets))
            if dataset.dataset_id == profile.auto_qa_dataset
            else dataset
            for dataset in datasets
        ]

    summary = QaSummary()
    for dataset in datasets:
        if dataset.role != "business":
            continue
        for record in dataset.records:
            if _has_value(record):
                summary.record_count += 1
            for cell in record.cells.values():
                if cell.review_status == VERIFIED:
                    summary.verified += 1
                elif cell.review_status == NEEDS_REVIEW:
                    summary.needs_review += 1
                elif cell.review_status == MISSING:
                    summary.missing += 1

    needs_review_records = sum(
        1
        for dataset in datasets
        if dataset.role == "business"
        for record in dataset.records
        if _has_value(record) and record.record_status == NEEDS_REVIEW
    )
    outcome = build_outcome_from_counts(
        record_count=summary.record_count,
        needs_review_count=needs_review_records,
        provenance=adapter_result.outcome_provenance,
    )

    return StagingWorkbook(
        document_id=document.id,
        document_filename=document.original_filename,
        profile=profile_descriptor(profile, document.id),
        outcome=ExtractionOutcomeModel(**outcome.model_dump()),
        datasets=datasets,
        qa_summary=summary,
        processing_metadata=metadata,
    )
