from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentQaReview(Base):
    """V3 QA Review sheet (docs/v3-schema-manifest.md §10) — a category-
    level checklist, one row per dataset area (Contract Summary, CLINs,
    Funding, Performance/Delivery, Attachments, Clauses, FAR References,
    DFARS), computed LAST from each dataset's own QA statuses. Not a
    granular per-record issue log (v3-implementation-plan.md decision #3).
    """

    __tablename__ = "document_qa_reviews"

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

    qa_check: Mapped[str] = mapped_column(String(80), nullable=False)

    result: Mapped[str] = mapped_column(String(10), nullable=False, default="REVIEW")

    details: Mapped[str] = mapped_column(Text, nullable=False, default="")

    action: Mapped[str] = mapped_column(String(300), nullable=False, default="None")

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
