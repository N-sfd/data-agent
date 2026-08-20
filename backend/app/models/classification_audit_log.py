from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ClassificationAuditLog(Base):
    __tablename__ = "classification_audit_log"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    field_changed: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    previous_value: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    new_value: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    changed_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
