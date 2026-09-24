"""Canonical V3 export API — the primary Results/export surface
(docs/v3-implementation-plan.md).

Quality-gate finding (security, release-blocking): these routes were
previously reachable with zero credentials — a random, unauthenticated
caller with only a document_id got back another user's full canonical V3
data. Gated the same way the codebase already gates comparable surfaces
(reviewed_export.py's export.read, target_corrections.py's
documents.view): `/v3` (the JSON the Results UI reads) requires
`documents.view` — granted to every role including `viewer` — and the
CSV/XLSX downloads require `export.read` (viewer does NOT have this,
matching reviewed_export.py's own split). This mirrors the existing RBAC
design, not a new one: `effective_rbac_enforced` is unconditionally True
in production and permissive in local dev, exactly as it already behaves
for every other gated endpoint in this app.

Known, deliberately out-of-scope for this pass: several OTHER
document-scoped read endpoints across the app (contract_analysis.py,
page_extraction.py, universal_extraction.py, and the base `GET
/api/documents/{id}`) have the same historical gap. `GET
/api/documents/{id}` is fixed alongside this file since it was the other
endpoint specifically verified against production; the rest need their
own dedicated, individually-tested audit rather than a blanket change
bundled into this fix.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_permission
from app.database.dependencies import get_database
from app.schemas.v3_document import NormalizedV3Document
from app.services.v3_export_builder import DATASET_NAMES, build_dataset_csv, build_v3_xlsx
from app.services.v3_reader import get_normalized_v3_document

router = APIRouter()


@router.get("/{document_id}/v3", response_model=NormalizedV3Document)
async def get_v3_document(
    document_id: str,
    database: Session = Depends(get_database),
    actor: ActorContext = Depends(require_permission("documents.view")),
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
    actor: ActorContext = Depends(require_permission("export.read")),
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
    actor: ActorContext = Depends(require_permission("export.read")),
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
