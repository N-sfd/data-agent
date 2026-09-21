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


class DocumentPage(Base):
    __tablename__ = "document_pages"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page_number",
            name="uq_document_page_number",
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

    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    page_label: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    native_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    ocr_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    final_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    form_fields_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    tables_json: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Word/line OCR geometry + confidence for scanned-layout association.
    # Soft-migrated; older rows remain NULL.
    ocr_layout_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    has_tables: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    has_form_fields: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_scanned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    text_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    extraction_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="native",
    )

    requires_ocr: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    ocr_attempted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    ocr_succeeded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    ocr_language: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    ocr_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    text_block_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    image_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    text_coverage_ratio: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    image_coverage_ratio: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    page_width: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    page_height: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    extraction_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
