"""Seed default actors for development and certification tests."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import DEFAULT_DEV_ACTOR_ID, hash_api_key
from app.models.actor import Actor

# Well-known test service key — only for local/test; hash stored in DB.
DEFAULT_SERVICE_API_KEY = "da-service-test-key-change-me"

DEFAULT_ACTORS: list[dict] = [
    {
        "id": DEFAULT_DEV_ACTOR_ID,
        "actor_type": "user",
        "display_name": "Dev Admin",
        "email": "admin@localhost",
        "role": "admin",
        "api_key_hash": None,
    },
    {
        "id": "actor-reviewer-default",
        "actor_type": "user",
        "display_name": "Default Reviewer",
        "email": "reviewer@localhost",
        "role": "reviewer",
        "api_key_hash": None,
    },
    {
        "id": "actor-analyst-default",
        "actor_type": "user",
        "display_name": "Default Analyst",
        "email": "analyst@localhost",
        "role": "analyst",
        "api_key_hash": None,
    },
    {
        "id": "actor-viewer-default",
        "actor_type": "user",
        "display_name": "Default Viewer",
        "email": "viewer@localhost",
        "role": "viewer",
        "api_key_hash": None,
    },
    {
        "id": "actor-service-default",
        "actor_type": "service",
        "display_name": "Default Service Account",
        "email": None,
        "role": "service_account",
        "api_key_hash": hash_api_key(DEFAULT_SERVICE_API_KEY),
    },
]


def seed_default_actors(database: Session) -> None:
    for spec in DEFAULT_ACTORS:
        existing = database.get(Actor, spec["id"])
        if existing is None:
            database.add(Actor(**spec, active=True))
        else:
            # Keep role/display in sync for seeded ids only.
            existing.role = spec["role"]
            existing.display_name = spec["display_name"]
            existing.actor_type = spec["actor_type"]
            existing.email = spec["email"]
            if spec["api_key_hash"]:
                existing.api_key_hash = spec["api_key_hash"]
            existing.active = True
    database.commit()


def ensure_actors_seeded(database: Session) -> None:
    count = database.scalar(select(Actor.id).limit(1))
    if count is None:
        seed_default_actors(database)
    else:
        # Always ensure the known defaults exist (idempotent upsert).
        seed_default_actors(database)
