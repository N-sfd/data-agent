from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentPerformancePeriod(Base):
    __tablename__ = "document_performance_periods"

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

    period_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")

    start_date: Mapped[str | None] = mapped_column(String(40), nullable=True)

    end_date: Mapped[str | None] = mapped_column(String(40), nullable=True)

    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- V3 Performance Delivery sheet columns (docs/v3-schema-manifest.md
    # §4) — merged with DocumentDeliverySchedule only at export/query time,
    # per the approved plan (lower-risk than a physical table merge). ---
    # Open set (not a fixed enum): "Period of Performance" | "FOB" |
    # "Commencement" | "Place of Performance" | "Task Order Content" | ...
    record_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    clin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # V3's "End / Timing" column mixes real dates and relative timing text
    # ("Within 15 days") in one column — end_date above stays a real date
    # when known; end_timing carries the free-text form actually exported.
    end_timing: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location_destination: Mapped[str | None] = mapped_column(String(300), nullable=True)
    requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    qa_status: Mapped[str | None] = mapped_column(String(80), nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
