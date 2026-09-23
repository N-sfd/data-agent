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

    # --- V3 CLINs sheet columns (docs/v3-schema-manifest.md §2) ---
    option_base: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pricing_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # quantity/unit_price/amount are numeric above but the V3 sheet allows a
    # literal placeholder string ("UNDEFINED", "NSP") when the source states
    # one instead of a number — stored separately so the numeric columns
    # never get coerced to 0/None to hold a non-numeric token.
    max_quantity_text: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fob: Mapped[str | None] = mapped_column(String(40), nullable=True)
    purchase_request: Mapped[str | None] = mapped_column(String(40), nullable=True)
    psc: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pop_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pop_end: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ship_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dodaac: Mapped[str | None] = mapped_column(String(10), nullable=True)
    qa_status: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # --- Internal-only hierarchy metadata (v3-implementation-plan.md
    # decision #1) — never exported to the V3 CLINs sheet; each CLIN/SLIN
    # still gets its own independent, fully-populated V3 row. ---
    slin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    parent_line_item: Mapped[str | None] = mapped_column(String(20), nullable=True)
    relationship: Mapped[str | None] = mapped_column(String(20), nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
