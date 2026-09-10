from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentDetectedTarget(Base):
    __tablename__ = "document_detected_targets"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "target_key",
            name="uq_document_detected_target_key",
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

    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    target_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="detected",
    )

    pages_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    source_examples_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    parent_section: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    columns_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    occurrence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    suggested_instruction: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Additive discovery metadata (group, value_type, method, labels, …)
    discovery_meta_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DocumentStructureSummary(Base):
    __tablename__ = "document_structure_summaries"

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )

    document_family: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    document_family_label: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    document_family_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    content_stats_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    detected_contacts_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    detected_obligations_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
