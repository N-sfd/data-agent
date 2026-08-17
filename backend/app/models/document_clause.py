from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentClause(Base):
    __tablename__ = "document_clauses"

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

    clause_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    classification: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    extracted_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    value_summary: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="",
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
