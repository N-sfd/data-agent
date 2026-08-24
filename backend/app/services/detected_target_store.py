from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document_detected_target import (
    DocumentDetectedTarget,
    DocumentStructureSummary,
)
from app.schemas.structure_detection import (
    ContentStats,
    DetectedField,
    DetectedTable,
    DetectedTarget,
    DetectionCounts,
    StructureDetectionResponse,
)


def persist_structure_detection(
    *,
    database: Session,
    result: StructureDetectionResponse,
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
            content_stats_json=result.content_stats.model_dump(),
            detected_contacts_json=result.detected_contacts,
            detected_obligations_json=result.detected_obligations,
            created_at=now,
            updated_at=now,
        )
    )

    for target in result.detected_targets + result.possible_targets:
        database.add(
            DocumentDetectedTarget(
                document_id=result.document_id,
                target_key=target.key,
                label=target.label,
                extraction_type=target.extraction_type,
                pages_json=target.pages,
                confidence=target.confidence,
                evidence_json=target.evidence,
                suggested_prompt=target.suggested_prompt,
                columns_json=target.columns,
                is_primary=target.confidence >= 0.75,
                created_at=now,
                updated_at=now,
            )
        )

    database.commit()


def load_structure_detection(
    *,
    database: Session,
    document_id: str,
) -> StructureDetectionResponse | None:
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
        DetectedTarget(
            key=row.target_key,
            label=row.label,
            extraction_type=row.extraction_type,  # type: ignore[arg-type]
            pages=list(row.pages_json or []),
            confidence=row.confidence,
            evidence=list(row.evidence_json or []),
            suggested_prompt=row.suggested_prompt,
            columns=list(row.columns_json or []),
        )
        for row in rows
    ]

    primary = [target for target in targets if target.confidence >= 0.75]
    possible = [target for target in targets if target.confidence < 0.75]

    stats = summary.content_stats_json or {}

    return StructureDetectionResponse(
        document_id=document_id,
        document_family=summary.document_family,
        document_family_label=summary.document_family_label,
        document_family_confidence=summary.document_family_confidence,
        detected_fields=[
            DetectedField(
                key=target.key,
                label=target.label,
                pages=target.pages,
            )
            for target in primary
            if target.extraction_type == "field"
        ],
        detected_tables=[
            DetectedTable(
                key=target.key,
                label=target.label,
                pages=target.pages,
                confidence=target.confidence,
                suggested_prompt=target.suggested_prompt,
                columns=target.columns,
            )
            for target in primary
            if target.extraction_type == "table"
        ],
        detected_contacts=list(summary.detected_contacts_json or []),
        detected_obligations=list(summary.detected_obligations_json or []),
        detected_targets=primary,
        possible_targets=possible,
        content_stats=ContentStats(
            tables=int(stats.get("tables", 0)),
            dates=int(stats.get("dates", 0)),
            currency_values=int(stats.get("currency_values", 0)),
            organizations=int(stats.get("organizations", 0)),
        ),
        counts=DetectionCounts(
            fields=sum(1 for t in primary if t.extraction_type == "field"),
            tables=sum(1 for t in primary if t.extraction_type == "table"),
            contacts=sum(1 for t in primary if t.extraction_type == "contact"),
            obligations=sum(
                1 for t in primary if t.extraction_type == "obligation"
            ),
            clauses=sum(1 for t in primary if t.extraction_type == "clause"),
            signatures=sum(
                1 for t in primary if t.extraction_type == "signature"
            ),
        ),
    )
