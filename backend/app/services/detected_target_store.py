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
)


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

    targets = [
        DocumentTarget(
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
        for row in rows
    ]

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
