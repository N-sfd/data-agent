from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentContact(Base):
    __tablename__ = "document_contacts"

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

    contact_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    role_title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    phone_area_code: Mapped[str | None] = mapped_column(String(5), nullable=True)

    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    phone_extension: Mapped[str | None] = mapped_column(String(10), nullable=True)

    email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
