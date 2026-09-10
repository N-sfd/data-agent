from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentExtractedTable(Base):
    """Durable table results from targeted extraction (Select All / jobs)."""

    __tablename__ = "document_extracted_tables"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "target_key",
            name="uq_document_extracted_table_key",
        ),
    )

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

    target_key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    columns_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    rows_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    pages_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    extraction_method: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    evidence_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    extraction_job_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
