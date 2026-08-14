from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PageTextBlock(Base):
    __tablename__ = "page_text_blocks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_page_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    block_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    block_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="text",
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    x0: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    y0: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    x1: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    y1: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    extraction_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="native",
    )
