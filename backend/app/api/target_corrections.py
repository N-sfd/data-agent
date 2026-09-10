from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database
from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.models.target_correction import TargetCorrection
from app.schemas.target_correction import (
    TargetCorrectionCreate,
    TargetCorrectionResponse,
)

router = APIRouter()


def _load_document_or_404(database: Session, document_id: str) -> Document:
    document = database.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@router.post(
    "/{document_id}/targets/{normalized_key}/corrections",
    response_model=TargetCorrectionResponse,
    status_code=201,
)
async def create_target_correction(
    document_id: str,
    normalized_key: str,
    request: TargetCorrectionCreate,
    database: Session = Depends(get_database),
) -> TargetCorrection:
    _load_document_or_404(database, document_id)

    correction = TargetCorrection(
        document_id=document_id,
        normalized_key=normalized_key,
        action=request.action,
        original_value=request.original_value,
        corrected_value=request.corrected_value,
        evidence_snapshot=(
            request.evidence.model_dump() if request.evidence else None
        ),
        changed_by=request.changed_by,
    )
    database.add(correction)

    # Keep durable intelligence record in sync so Explorer/reopen see truth.
    field = database.scalar(
        select(DocumentMetadataField).where(
            DocumentMetadataField.document_id == document_id,
            DocumentMetadataField.field_key == normalized_key,
            DocumentMetadataField.extraction_source == "target",
        )
    )
    if field is not None:
        if request.action == "edit" and request.corrected_value is not None:
            field.value = str(request.corrected_value)
            field.review_status = "edited"
        elif request.action == "verify":
            field.verified = True
            field.human_approved = True
            field.review_status = "accepted"

    database.commit()
    database.refresh(correction)
    return correction


@router.get(
    "/{document_id}/corrections",
    response_model=list[TargetCorrectionResponse],
)
async def list_target_corrections(
    document_id: str,
    database: Session = Depends(get_database),
) -> list[TargetCorrection]:
    _load_document_or_404(database, document_id)

    rows = database.scalars(
        select(TargetCorrection)
        .where(TargetCorrection.document_id == document_id)
        .order_by(TargetCorrection.created_at.asc())
    ).all()

    latest_by_key: dict[str, TargetCorrection] = {}
    for row in rows:
        latest_by_key[row.normalized_key] = row

    return list(latest_by_key.values())
