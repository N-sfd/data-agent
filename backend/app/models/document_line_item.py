from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentLineItem(Base):
    __tablename__ = "document_line_items"

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

    clin: Mapped[str | None] = mapped_column(String(20), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)

    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)

    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    # True for IDIQ-style "Line Items" (Max Qty / Max Amount); False for an
    # awarded "Schedule of Prices" row — same shape, different semantics.
    is_maximum: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    period_label: Mapped[str | None] = mapped_column(String(80), nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
