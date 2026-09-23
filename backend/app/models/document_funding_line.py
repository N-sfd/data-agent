from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentFundingLine(Base):
    __tablename__ = "document_funding_lines"

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

    acrn: Mapped[str | None] = mapped_column(String(10), nullable=True)

    line_of_accounting: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- V3 Funding sheet columns (docs/v3-schema-manifest.md §3) ---
    # Open vocabulary (decision #4): "Basic IDIQ" | "Task Orders" |
    # "Minimum Guarantee" | ... — distinguishes an actual obligated-funding
    # fact from task-order/future-funding requirement narrative; both get a
    # row, never silently dropped.
    funding_level: Mapped[str | None] = mapped_column(String(60), nullable=True)
    clin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    funding_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    accounting_appropriation: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_request: Mapped[str | None] = mapped_column(String(40), nullable=True)
    qa_status: Mapped[str | None] = mapped_column(String(80), nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
