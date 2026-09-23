from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentAttachment(Base):
    """V3 Attachments sheet (docs/v3-schema-manifest.md §5)."""

    __tablename__ = "document_attachments"

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

    attachment_reference: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    title_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Free text, not boolean, per the ground-truth sheet ("Not present
    # among the three extracted portfolio PDFs", "No — expressly
    # excluded...").
    included_in_portfolio: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Free text, allowed outside the standard dropdown (e.g. "Referenced;
    # attachment bytes not available in extracted portfolio set").
    qa_status: Mapped[str | None] = mapped_column(String(120), nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
