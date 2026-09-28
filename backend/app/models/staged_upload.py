from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class StagedUpload(Base):
    """Who owns an upload that is staged but not yet a Document — a
    duplicate awaiting "use existing / upload anyway", or a PDF Portfolio
    awaiting a file choice. Lets document isolation check the follow-up
    request by owner instead of trusting that the staged id is unguessable."""

    __tablename__ = "staged_uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_workspace: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
