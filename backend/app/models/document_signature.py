from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentSignature(Base):
    __tablename__ = "document_signatures"

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

    party_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    signatory_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="",
    )

    signatory_title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="",
    )

    signed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    signature_date: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    evidence_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
