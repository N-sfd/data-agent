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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentMetadataField(Base):
    __tablename__ = "document_metadata_fields"

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

    field_group: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    field_key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    confidence_band: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    value_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    extraction_method: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="label_value",
    )

    display_method: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    evidence_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    human_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    original_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    # contract = analyze-contract path; target = Select All / jobs/extract;
    # v3 = structure_classifier/candidate_router pipeline (V3 All Fields sheet)
    extraction_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="contract",
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
