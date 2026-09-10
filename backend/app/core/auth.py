"""Resolve the current actor and enforce permissions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.entra import (
    claims_to_actor_fields,
    looks_like_jwt,
    validate_entra_access_token,
)
from app.core.rbac import Permission, role_has_permission
from app.database.dependencies import get_database
from app.models.actor import Actor

DEFAULT_DEV_ACTOR_ID = "actor-admin-default"


@dataclass(frozen=True)
class ActorContext:
    id: str
    actor_type: str
    role: str
    display_name: str

    def has(self, permission: Permission) -> bool:
        return role_has_permission(self.role, permission)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def actor_to_context(actor: Actor) -> ActorContext:
    return ActorContext(
        id=actor.id,
        actor_type=actor.actor_type,
        role=actor.role,
        display_name=actor.display_name,
    )


def upsert_actor_from_entra(
    database: Session,
    fields: dict,
) -> Actor:
    actor = database.get(Actor, fields["id"])
    if actor is None:
        actor = Actor(
            id=fields["id"],
            actor_type=fields["actor_type"],
            display_name=fields["display_name"],
            email=fields.get("email"),
            role=fields["role"],
            active=True,
        )
        database.add(actor)
    else:
        actor.display_name = fields["display_name"]
        actor.email = fields.get("email")
        actor.role = fields["role"]
        actor.actor_type = fields["actor_type"]
        actor.active = True
    database.commit()
    database.refresh(actor)
    return actor


def resolve_actor(
    database: Session,
    *,
    actor_id_header: str | None,
    authorization: str | None,
) -> ActorContext:
    settings = get_settings()
    enforced = settings.effective_rbac_enforced

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            # 1) Entra JWT (when configured)
            if settings.entra_configured and looks_like_jwt(token):
                try:
                    claims = validate_entra_access_token(token)
                    fields = claims_to_actor_fields(claims)
                    actor = upsert_actor_from_entra(database, fields)
                    return actor_to_context(actor)
                except ValueError as exc:
                    # Fall through to service API key only if token is not JWT-shaped
                    # For JWT-shaped tokens under Entra, fail closed when enforced.
                    if enforced:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=str(exc),
                        ) from exc

            # 2) Service account API key
            digest = hash_api_key(token)
            actor = database.scalar(
                select(Actor).where(
                    Actor.api_key_hash == digest,
                    Actor.active.is_(True),
                )
            )
            if actor is not None:
                return actor_to_context(actor)

            if enforced:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid bearer credential.",
                )

    # X-Actor-Id is a local/dev convenience — never trusted when RBAC is enforced
    # (prevents spoofing once Entra / API keys are required).
    if actor_id_header and not enforced:
        actor = database.get(Actor, actor_id_header.strip())
        if actor is not None and actor.active:
            return actor_to_context(actor)

    if enforced:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authentication required. Use Authorization: Bearer "
                "<Entra access token or service API key>."
            ),
        )

    # Dev / test fallback — seeded admin so existing suites keep working.
    fallback = database.get(Actor, DEFAULT_DEV_ACTOR_ID)
    if fallback is not None and fallback.active:
        return actor_to_context(fallback)

    return ActorContext(
        id=DEFAULT_DEV_ACTOR_ID,
        actor_type="user",
        role="admin",
        display_name="Dev Admin",
    )


async def get_current_actor(
    database: Session = Depends(get_database),
    x_actor_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> ActorContext:
    return resolve_actor(
        database,
        actor_id_header=x_actor_id,
        authorization=authorization,
    )


def require_permission(permission: Permission):
    """FastAPI dependency factory — 403 when the actor lacks ``permission``."""

    async def _check(
        actor: ActorContext = Depends(get_current_actor),
    ) -> ActorContext:
        if not actor.has(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return actor

    return _check
