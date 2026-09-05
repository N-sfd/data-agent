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


class CustomTargetError(Exception):
    pass


def _slugify_label(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug or "custom_field"


def _row_to_target(document_id: str, row: DocumentDetectedTarget) -> DocumentTarget:
    return DocumentTarget(
        id=f"{document_id}:{row.target_key}",
        key=row.target_key,
        label=row.label,
        target_type=row.target_type,  # type: ignore[arg-type]
        page_numbers=list(row.pages_json or []),
        confidence=row.confidence,
        source_examples=list(row.source_examples_json or []),
        parent_section=row.parent_section,
        columns=list(row.columns_json or []),
        occurrence_count=row.occurrence_count,
        suggested_instruction=row.suggested_instruction,
        source=row.source,  # type: ignore[arg-type]
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

    base_key = f"custom_{_slugify_label(label)}"
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
    row = DocumentDetectedTarget(
        document_id=document_id,
        target_key=target_key,
        label=label,
        target_type=target_type,
        source="custom",
        pages_json=[],
        confidence=1.0,
        source_examples_json=[],
        parent_section=None,
        columns_json=[],
        occurrence_count=1,
        suggested_instruction=f"Extract the {label}.",
        is_primary=True,
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
    row.label = label
    row.suggested_instruction = f"Extract the {label}."
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
    database.execute(
        delete(DocumentDetectedTarget).where(
            DocumentDetectedTarget.document_id == result.document_id
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
        database.add(
            DocumentDetectedTarget(
                document_id=result.document_id,
                target_key=target.key,
                label=target.label,
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
