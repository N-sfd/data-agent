"""Actor identity model for RBAC and actor-aware audit."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Actor(Base):
    """Application principal — human user or service account.

    Not a full IdP. Resolve via ``X-Actor-Id`` or Bearer API key until
    Entra/OAuth lands; audit columns attach identity without redesign.
    """

    __tablename__ = "actors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    actor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
    )

    display_name: Mapped[str] = mapped_column(String(120), nullable=False)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    api_key_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
