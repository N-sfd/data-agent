import re
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document_detected_target import (
    DocumentDetectedTarget,
    DocumentStructureSummary,
)
from app.schemas.document_target import (
    DiscoverSchemaResponse,
    DocumentTarget,
    TargetType,
)
from app.services.discovery_enrichment import (
    assign_discovery_group,
    canonical_display_name,
    infer_value_type,
)


class CustomTargetError(Exception):
    pass


def _slugify_label(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug or "custom_field"


def _meta_from_target(target: DocumentTarget) -> dict:
    return {
        "display_name": target.display_name or target.label,
        "group": target.group,
        "value_type": target.value_type,
        "discovery_method": target.discovery_method,
        "source_labels": list(target.source_labels or []),
        "is_custom": target.is_custom or target.source == "custom",
        "is_internal": target.is_internal,
        "selectable": target.selectable,
        "description": target.description,
    }


def _row_to_target(document_id: str, row: DocumentDetectedTarget) -> DocumentTarget:
    meta = dict(row.discovery_meta_json or {})
    source = row.source  # type: ignore[assignment]
    label = row.label
    display = meta.get("display_name") or label
    target_type = row.target_type  # type: ignore[assignment]

    return DocumentTarget(
        id=f"{document_id}:{row.target_key}",
        key=row.target_key,
        label=display,
        target_type=target_type,  # type: ignore[arg-type]
        page_numbers=list(row.pages_json or []),
        confidence=row.confidence,
        source_examples=list(row.source_examples_json or []),
        parent_section=row.parent_section,
        columns=list(row.columns_json or []),
        occurrence_count=row.occurrence_count,
        suggested_instruction=row.suggested_instruction,
        source=source,  # type: ignore[arg-type]
        display_name=display,
        group=meta.get("group")
        or assign_discovery_group(label=display, target_type=str(target_type)),
        value_type=meta.get("value_type")
        or infer_value_type(label=display, target_type=str(target_type)),
        discovery_method=meta.get("discovery_method"),
        source_labels=list(meta.get("source_labels") or []),
        is_custom=bool(meta.get("is_custom", source == "custom")),
        is_internal=bool(meta.get("is_internal", False)),
        selectable=bool(meta.get("selectable", True)),
        description=meta.get("description") or row.suggested_instruction,
    )


def add_custom_target(
    *,
    database: Session,
    document_id: str,
    label: str,
    target_type: TargetType = "custom",
) -> DocumentTarget:
    """Add a single user-defined target without disturbing the rest of
    the discovered schema (unlike persist_document_targets, which
    replaces the whole set — this only inserts one row)."""

    if database.get(DocumentStructureSummary, document_id) is None:
        raise CustomTargetError(
            "Run schema discovery before adding a custom field."
        )

    display = canonical_display_name(label)
    base_key = f"custom_{_slugify_label(display)}"
    target_key = base_key
    suffix = 1
    while database.scalar(
        select(DocumentDetectedTarget.id).where(
            DocumentDetectedTarget.document_id == document_id,
            DocumentDetectedTarget.target_key == target_key,
        )
    ):
        suffix += 1
        target_key = f"{base_key}_{suffix}"

    now = datetime.now(timezone.utc)
    target = DocumentTarget(
        id=f"{document_id}:{target_key}",
        key=target_key,
        label=display,
        display_name=display,
        target_type=target_type,
        page_numbers=[],
        confidence=1.0,
        source_examples=[],
        columns=[],
        occurrence_count=1,
        suggested_instruction=f"Extract the {display}.",
        source="custom",
        group=assign_discovery_group(label=display, target_type=target_type),
        value_type=infer_value_type(label=display, target_type=target_type),
        discovery_method="custom",
        source_labels=[label],
        is_custom=True,
        is_internal=False,
        selectable=True,
        description=f"Extract the {display}.",
    )
    row = DocumentDetectedTarget(
        document_id=document_id,
        target_key=target_key,
        label=display,
        target_type=target_type,
        source="custom",
        pages_json=[],
        confidence=1.0,
        source_examples_json=[],
        parent_section=None,
        columns_json=[],
        occurrence_count=1,
        suggested_instruction=target.suggested_instruction,
        is_primary=True,
        discovery_meta_json=_meta_from_target(target),
        created_at=now,
        updated_at=now,
    )
    database.add(row)
    database.commit()
    database.refresh(row)

    return _row_to_target(document_id, row)


def _get_custom_row(
    database: Session, document_id: str, target_key: str
) -> DocumentDetectedTarget:
    row = database.scalar(
        select(DocumentDetectedTarget).where(
            DocumentDetectedTarget.document_id == document_id,
            DocumentDetectedTarget.target_key == target_key,
        )
    )
    if row is None or row.source != "custom":
        raise CustomTargetError("Custom field not found.")
    return row


def rename_custom_target(
    *,
    database: Session,
    document_id: str,
    target_key: str,
    label: str,
) -> DocumentTarget:
    row = _get_custom_row(database, document_id, target_key)
    display = canonical_display_name(label)
    row.label = display
    row.suggested_instruction = f"Extract the {display}."
    meta = dict(row.discovery_meta_json or {})
    meta.update(
        {
            "display_name": display,
            "source_labels": [label],
            "description": row.suggested_instruction,
            "is_custom": True,
            "group": assign_discovery_group(
                label=display, target_type=row.target_type
            ),
        }
    )
    row.discovery_meta_json = meta
    database.commit()
    database.refresh(row)
    return _row_to_target(document_id, row)


def delete_custom_target(
    *,
    database: Session,
    document_id: str,
    target_key: str,
) -> None:
    row = _get_custom_row(database, document_id, target_key)
    database.delete(row)
    database.commit()


def persist_document_targets(
    *,
    database: Session,
    result: DiscoverSchemaResponse,
) -> None:
    # Preserve user custom fields across rediscovery.
    custom_rows = list(
        database.scalars(
            select(DocumentDetectedTarget).where(
                DocumentDetectedTarget.document_id == result.document_id,
                DocumentDetectedTarget.source == "custom",
            )
        )
    )
    custom_keys = {row.target_key for row in custom_rows}

    database.execute(
        delete(DocumentDetectedTarget).where(
            DocumentDetectedTarget.document_id == result.document_id,
            DocumentDetectedTarget.source != "custom",
        )
    )
    database.execute(
        delete(DocumentStructureSummary).where(
            DocumentStructureSummary.document_id == result.document_id
        )
    )

    now = datetime.now(timezone.utc)

    database.add(
        DocumentStructureSummary(
            document_id=result.document_id,
            document_family=result.document_family,
            document_family_label=result.document_family_label,
            document_family_confidence=result.document_family_confidence,
            content_stats_json={},
            detected_contacts_json=[],
            detected_obligations_json=[],
            created_at=now,
            updated_at=now,
        )
    )

    for target in result.targets:
        if target.key in custom_keys:
            continue
        database.add(
            DocumentDetectedTarget(
                document_id=result.document_id,
                target_key=target.key,
                label=target.display_name or target.label,
                target_type=target.target_type,
                source=target.source,
                pages_json=target.page_numbers,
                confidence=target.confidence,
                source_examples_json=target.source_examples,
                parent_section=target.parent_section,
                columns_json=target.columns,
                occurrence_count=target.occurrence_count,
                suggested_instruction=target.suggested_instruction,
                is_primary=target.confidence >= 0.75,
                discovery_meta_json=_meta_from_target(target),
                created_at=now,
                updated_at=now,
            )
        )

    database.commit()


def load_document_targets(
    *,
    database: Session,
    document_id: str,
) -> DiscoverSchemaResponse | None:
    summary = database.get(DocumentStructureSummary, document_id)

    if summary is None:
        return None

    rows = list(
        database.scalars(
            select(DocumentDetectedTarget)
            .where(DocumentDetectedTarget.document_id == document_id)
            .order_by(DocumentDetectedTarget.id)
        )
    )

    targets = [_row_to_target(document_id, row) for row in rows]

    counts_by_type: dict[str, int] = {}
    for target in targets:
        counts_by_type[target.target_type] = (
            counts_by_type.get(target.target_type, 0) + 1
        )

    return DiscoverSchemaResponse(
        document_id=document_id,
        document_family=summary.document_family,
        document_family_label=summary.document_family_label,
        document_family_confidence=summary.document_family_confidence,
        targets=targets,
        counts_by_type=counts_by_type,
        generated_at=summary.updated_at.replace(tzinfo=timezone.utc)
        if summary.updated_at.tzinfo is None
        else summary.updated_at,
    )
