"""Persist targeted extraction results as durable intelligence records.

Repository / Field Explorer / reopen must reconstruct from PostgreSQL,
not React state or job blobs alone.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_extracted_table import DocumentExtractedTable
from app.models.document_metadata_field import DocumentMetadataField
from app.schemas.document_target import (
    ExtractTargetsResponse,
    ScalarTargetResult,
    TableTargetResult,
)
from app.schemas.universal_extraction import SourceEvidence
from app.services.detected_target_store import load_document_targets


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _evidence_dict(evidence: Any) -> dict:
    if evidence is None:
        return {
            "page_number": 1,
            "source_text": "",
            "source_reference": "",
        }
    if isinstance(evidence, SourceEvidence):
        return evidence.model_dump()
    if isinstance(evidence, dict):
        return evidence
    return {
        "page_number": 1,
        "source_text": str(evidence),
        "source_reference": "",
    }


def persist_target_extraction_results(
    *,
    database: Session,
    document_id: str,
    scalars: list[ScalarTargetResult] | list[dict],
    tables: list[TableTargetResult] | list[dict],
    extraction_job_id: int | None = None,
) -> None:
    """Upsert scalars + tables from a completed targeted extraction."""

    discovered = load_document_targets(database=database, document_id=document_id)
    label_by_key: dict[str, str] = {}
    group_by_key: dict[str, str] = {}
    value_type_by_key: dict[str, str] = {}
    if discovered:
        for target in discovered.targets:
            label_by_key[target.key] = target.display_name or target.label
            if target.group:
                group_by_key[target.key] = target.group
            if target.value_type:
                value_type_by_key[target.key] = target.value_type

    now = datetime.now(timezone.utc)

    for item in scalars:
        if isinstance(item, dict):
            scalar = ScalarTargetResult.model_validate(item)
        else:
            scalar = item

        key = scalar.normalized_key
        value = _stringify_value(scalar.value)
        evidence = _evidence_dict(scalar.evidence)

        existing = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.field_key == key,
                DocumentMetadataField.extraction_source == "target",
            )
        )

        label = label_by_key.get(key) or scalar.target or key
        group = group_by_key.get(key) or "extracted"
        value_type = value_type_by_key.get(key) or "string"

        if existing is None:
            database.add(
                DocumentMetadataField(
                    document_id=document_id,
                    field_group=group[:30],
                    field_key=key[:120],
                    label=label[:255],
                    value=value,
                    original_value=value,
                    confidence=scalar.confidence,
                    confidence_band=scalar.confidence_band,
                    value_type=value_type,
                    extraction_method=(scalar.extraction_method or "label_value")[
                        :40
                    ],
                    display_method=(scalar.display_method or None),
                    evidence_json=evidence,
                    verified=bool(scalar.verified),
                    review_status="pending",
                    extraction_source="target",
                    extraction_job_id=extraction_job_id,
                    extracted_at=now,
                )
            )
        else:
            # Preserve human review edits unless still pending/unreviewed.
            if existing.review_status in {"pending", "accepted"}:
                existing.value = value
                if not existing.original_value:
                    existing.original_value = value
            existing.label = label[:255]
            existing.field_group = group[:30]
            existing.confidence = scalar.confidence
            existing.confidence_band = scalar.confidence_band
            existing.value_type = value_type
            existing.extraction_method = (
                scalar.extraction_method or existing.extraction_method
            )[:40]
            existing.display_method = scalar.display_method or existing.display_method
            existing.evidence_json = evidence
            existing.verified = bool(scalar.verified)
            existing.extraction_job_id = extraction_job_id
            existing.extracted_at = now

    for item in tables:
        if isinstance(item, dict):
            table = TableTargetResult.model_validate(item)
        else:
            table = item

        # TableTargetResult.target is display label; prefer slug from target id.
        target_key = (
            table.target.lower().replace(" ", "_")[:120]
            if table.target
            else "table"
        )
        # Prefer matching discovered table keys when label matches.
        if discovered:
            for discovered_target in discovered.targets:
                if (
                    discovered_target.target_type == "table"
                    and discovered_target.label == table.target
                ):
                    target_key = discovered_target.key
                    break

        existing_table = database.scalar(
            select(DocumentExtractedTable).where(
                DocumentExtractedTable.document_id == document_id,
                DocumentExtractedTable.target_key == target_key,
            )
        )
        if existing_table is None:
            database.add(
                DocumentExtractedTable(
                    document_id=document_id,
                    target_key=target_key,
                    display_name=table.target,
                    columns_json=list(table.columns or []),
                    rows_json=list(table.rows or []),
                    pages_json=list(table.pages or []),
                    extraction_method="table",
                    confidence=None,
                    evidence_json=None,
                    extraction_job_id=extraction_job_id,
                    extracted_at=now,
                )
            )
        else:
            existing_table.display_name = table.target
            existing_table.columns_json = list(table.columns or [])
            existing_table.rows_json = list(table.rows or [])
            existing_table.pages_json = list(table.pages or [])
            existing_table.extraction_job_id = extraction_job_id
            existing_table.extracted_at = now

    database.commit()


def load_persisted_extract_results(
    *,
    database: Session,
    document_id: str,
) -> ExtractTargetsResponse | None:
    """Rebuild ExtractTargetsResponse from durable rows (no re-extract)."""

    scalar_rows = list(
        database.scalars(
            select(DocumentMetadataField)
            .where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.extraction_source == "target",
            )
            .order_by(DocumentMetadataField.id)
        )
    )
    table_rows = list(
        database.scalars(
            select(DocumentExtractedTable)
            .where(DocumentExtractedTable.document_id == document_id)
            .order_by(DocumentExtractedTable.id)
        )
    )

    if not scalar_rows and not table_rows:
        return None

    scalars: list[ScalarTargetResult] = []
    for row in scalar_rows:
        evidence = SourceEvidence.model_validate(
            row.evidence_json
            or {
                "page_number": 1,
                "source_text": "",
                "source_reference": "",
            }
        )
        band = row.confidence_band or (
            "high"
            if row.confidence >= 0.85
            else "medium"
            if row.confidence >= 0.6
            else "low"
        )
        scalars.append(
            ScalarTargetResult(
                target=row.label,
                normalized_key=row.field_key,
                value=row.value,
                page=evidence.page_number,
                confidence=row.confidence,
                confidence_band=band,  # type: ignore[arg-type]
                verified=row.verified,
                extraction_method=row.extraction_method,
                display_method=row.display_method or "",
                evidence=evidence,
            )
        )

    tables = [
        TableTargetResult(
            target=row.display_name,
            columns=list(row.columns_json or []),
            rows=list(row.rows_json or []),
            pages=list(row.pages_json or []),
        )
        for row in table_rows
    ]

    return ExtractTargetsResponse(
        document_id=document_id,
        scalars=scalars,
        tables=tables,
        unresolved_targets=[],
        warnings=[],
    )


def list_target_metadata_fields(
    *,
    database: Session,
    document_id: str,
) -> list[DocumentMetadataField]:
    return list(
        database.scalars(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.extraction_source == "target",
            )
        )
    )
