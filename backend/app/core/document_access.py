"""Document isolation between browser workspaces.

Anonymous callers (the built-in ``workspace`` role) are scoped to the
documents uploaded from their own workspace — identified by a secret token
the browser generates and sends as ``X-Workspace-Token``; only its hash is
stored (documents.owner_workspace). Knowing another document's UUID grants
nothing. Real credentials (admins, reviewers, service keys, Entra users)
keep their role-based access to every document.

Enforcement is attached to whole routers at mount time (app/main.py), so
every ``/{document_id}/…`` route — including ones added later — is covered
without per-route code. Cross-document endpoints (lists, search, dashboard,
jobs, duplicate detection, relationship matching) filter with
``scope_documents``. A document outside the caller's workspace answers 404,
not 403, so its existence is not disclosed.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, get_current_actor
from app.database.dependencies import get_database
from app.models.document import Document
from app.models.staged_upload import StagedUpload

_NOT_FOUND = "Document not found."


def workspace_scoped(actor: ActorContext) -> bool:
    return actor.role == "workspace"


def can_access_document(actor: ActorContext, document: Document) -> bool:
    if not workspace_scoped(actor):
        return True
    return actor.workspace is not None and document.owner_workspace == actor.workspace


def scope_documents(statement, actor: ActorContext):
    """Restrict a query selecting/joining Document to the caller's
    workspace (a no-op for real credentials)."""

    if not workspace_scoped(actor):
        return statement
    if actor.workspace is None:
        return statement.where(Document.id.is_(None))  # no workspace → nothing
    return statement.where(Document.owner_workspace == actor.workspace)


def require_document_access(database: Session, actor: ActorContext, document_id: str) -> Document | None:
    """The document if the caller may reach it; 404 otherwise. Returns None
    for an id that is only a staged upload the caller owns."""

    document = database.get(Document, str(document_id))
    if document is not None:
        if not can_access_document(actor, document):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
        return document
    if workspace_scoped(actor):
        staged = database.get(StagedUpload, str(document_id))
        if staged is None or actor.workspace is None or staged.owner_workspace != actor.workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return None


async def enforce_document_access(
    request: Request,
    actor: ActorContext = Depends(get_current_actor),
    database: Session = Depends(get_database),
) -> None:
    """Router-level dependency: any route with a ``document_id`` path
    parameter is checked before its handler runs."""

    document_id = request.path_params.get("document_id")
    if document_id is None or not workspace_scoped(actor):
        return
    require_document_access(database, actor, str(document_id))


def record_staged_upload(database: Session, staged_id: str, actor: ActorContext) -> None:
    """Remember who owns a staged (not yet created) upload."""

    if database.get(StagedUpload, staged_id) is None:
        database.add(StagedUpload(id=staged_id, owner_workspace=actor.workspace))
        database.commit()


def staged_owner(database: Session, staged_id: str) -> str | None:
    staged = database.get(StagedUpload, str(staged_id))
    return staged.owner_workspace if staged else None
