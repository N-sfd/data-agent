from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database
from app.models.extraction_model import ExtractionField, ExtractionModel
from app.schemas.extraction_models import (
    ExtractionFieldCreate,
    ExtractionFieldResponse,
    ExtractionModelCreate,
    ExtractionModelResponse,
)

router = APIRouter()


def _get_fields(
    database: Session, model_id: int
) -> list[ExtractionField]:
    return list(
        database.scalars(
            select(ExtractionField)
            .where(ExtractionField.model_id == model_id)
            .order_by(ExtractionField.created_at)
        )
    )


def _to_response(
    database: Session, model: ExtractionModel
) -> ExtractionModelResponse:
    return ExtractionModelResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        document_types=model.document_types or ["*"],
        created_at=model.created_at,
        fields=[
            ExtractionFieldResponse(
                id=field.id,
                model_id=field.model_id,
                field_name=field.field_name,
                description=field.description,
                data_type=field.data_type,
                created_at=field.created_at,
            )
            for field in _get_fields(database, model.id)
        ],
    )


@router.get("", response_model=list[ExtractionModelResponse])
async def list_extraction_models(
    document_type: str | None = None,
    database: Session = Depends(get_database),
) -> list[ExtractionModelResponse]:
    models = list(
        database.scalars(
            select(ExtractionModel).order_by(
                ExtractionModel.created_at.desc()
            )
        )
    )

    if document_type:
        models = [
            model
            for model in models
            if document_type in (model.document_types or ["*"])
            or "*" in (model.document_types or ["*"])
        ]

    return [_to_response(database, model) for model in models]


@router.post("", response_model=ExtractionModelResponse, status_code=201)
async def create_extraction_model(
    payload: ExtractionModelCreate,
    database: Session = Depends(get_database),
) -> ExtractionModelResponse:
    model = ExtractionModel(
        name=payload.name,
        description=payload.description,
        document_types=payload.document_types or ["*"],
    )

    database.add(model)
    database.commit()
    database.refresh(model)

    return _to_response(database, model)


@router.delete("/{model_id}", status_code=204)
async def delete_extraction_model(
    model_id: int,
    database: Session = Depends(get_database),
) -> None:
    model = database.get(ExtractionModel, model_id)

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Extraction model not found.",
        )

    database.delete(model)
    database.commit()


@router.post(
    "/{model_id}/fields",
    response_model=ExtractionModelResponse,
    status_code=201,
)
async def add_extraction_field(
    model_id: int,
    payload: ExtractionFieldCreate,
    database: Session = Depends(get_database),
) -> ExtractionModelResponse:
    model = database.get(ExtractionModel, model_id)

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Extraction model not found.",
        )

    database.add(
        ExtractionField(
            model_id=model_id,
            field_name=payload.field_name,
            description=payload.description,
            data_type=payload.data_type,
        )
    )
    database.commit()
    database.refresh(model)

    return _to_response(database, model)


@router.delete(
    "/{model_id}/fields/{field_id}",
    response_model=ExtractionModelResponse,
)
async def delete_extraction_field(
    model_id: int,
    field_id: int,
    database: Session = Depends(get_database),
) -> ExtractionModelResponse:
    model = database.get(ExtractionModel, model_id)

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Extraction model not found.",
        )

    field = database.get(ExtractionField, field_id)

    if field is None or field.model_id != model_id:
        raise HTTPException(
            status_code=404,
            detail="Extraction field not found.",
        )

    database.delete(field)
    database.commit()
    database.refresh(model)

    return _to_response(database, model)
