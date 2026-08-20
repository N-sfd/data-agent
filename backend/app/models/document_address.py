from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentAddress(Base):
    __tablename__ = "document_addresses"

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

    # "offeror" | "remittance" | "ship_to" | "invoice_destination" | "other"
    address_type: Mapped[str] = mapped_column(String(40), nullable=False)

    organization_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    street: Mapped[str | None] = mapped_column(String(300), nullable=True)

    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    state: Mapped[str | None] = mapped_column(String(50), nullable=True)

    zip_code: Mapped[str | None] = mapped_column(String(15), nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
