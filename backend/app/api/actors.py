"""Actor directory — list principals and current identity."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, get_current_actor, require_permission
from app.core.rbac import ROLE_PERMISSIONS
from app.database.dependencies import get_database
from app.models.actor import Actor

router = APIRouter()


class ActorResponse(BaseModel):
    id: str
    actor_type: str
    display_name: str
    email: str | None
    role: str
    active: bool
    permissions: list[str]


def _to_response(actor: Actor) -> ActorResponse:
    perms = sorted(ROLE_PERMISSIONS.get(actor.role, frozenset()))  # type: ignore[arg-type]
    return ActorResponse(
        id=actor.id,
        actor_type=actor.actor_type,
        display_name=actor.display_name,
        email=actor.email,
        role=actor.role,
        active=actor.active,
        permissions=list(perms),
    )


@router.get("/me", response_model=ActorResponse)
async def get_me(
    actor: ActorContext = Depends(get_current_actor),
    database: Session = Depends(get_database),
) -> ActorResponse:
    row = database.get(Actor, actor.id)
    if row is None:
        return ActorResponse(
            id=actor.id,
            actor_type=actor.actor_type,
            display_name=actor.display_name,
            email=None,
            role=actor.role,
            active=True,
            permissions=sorted(ROLE_PERMISSIONS.get(actor.role, frozenset())),  # type: ignore[arg-type]
        )
    return _to_response(row)


@router.get("", response_model=list[ActorResponse])
async def list_actors(
    database: Session = Depends(get_database),
    actor: ActorContext = Depends(require_permission("admin.users")),
) -> list[ActorResponse]:
    rows = database.scalars(select(Actor).order_by(Actor.display_name.asc())).all()
    return [_to_response(row) for row in rows]
