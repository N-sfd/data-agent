"""Canonical V3 export API — the primary Results/export surface
(docs/v3-implementation-plan.md). Deliberately NOT behind `require_permission`
(unlike reviewed_export.py's endpoints): those 401 in the browser session the
primary Results page runs in (see frontend/components/extraction/
target-results.tsx's own comment on why it avoids them), which is exactly
the gap this rewiring closes — the V3 pipeline runs inside the same
unauthenticated job flow the frontend already calls successfully.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.dependencies import get_database
from app.schemas.v3_document import NormalizedV3Document
from app.services.v3_export_builder import DATASET_NAMES, build_dataset_csv, build_v3_xlsx
from app.services.v3_reader import get_normalized_v3_document

router = APIRouter()


@router.get("/{document_id}/v3", response_model=NormalizedV3Document)
async def get_v3_document(
    document_id: str,
    database: Session = Depends(get_database),
) -> NormalizedV3Document:
    try:
        return get_normalized_v3_document(database, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{document_id}/v3/{dataset}.csv")
async def get_v3_dataset_csv(
    document_id: str,
    dataset: str,
    database: Session = Depends(get_database),
) -> Response:
    if dataset not in DATASET_NAMES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown V3 dataset {dataset!r}. Valid: {', '.join(DATASET_NAMES)}",
        )
    try:
        doc = get_normalized_v3_document(database, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    csv_text = build_dataset_csv(doc, dataset)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{dataset}.csv"'
        },
    )


@router.get("/{document_id}/v3/export.xlsx")
async def get_v3_export_xlsx(
    document_id: str,
    database: Session = Depends(get_database),
) -> Response:
    try:
        doc = get_normalized_v3_document(database, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    workbook_bytes = build_v3_xlsx(doc)
    filename = f"{doc.document_filename.rsplit('.', 1)[0]}_V3.xlsx"
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
