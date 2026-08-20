from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentAmendmentHistory(Base):
    """
    A single contract's own internal modification history, as extracted
    from its own text (e.g. an SF30 continuation table). Distinct from
    Document.parent_document_id / parent_relationship_type, which detects
    that an entire UPLOADED DOCUMENT is an amendment to a different
    parent document.
    """

    __tablename__ = "document_amendment_history"

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

    row_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    amendment_number: Mapped[str] = mapped_column(String(30), nullable=False, default="")

    effective_date: Mapped[str | None] = mapped_column(String(40), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
