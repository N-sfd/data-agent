from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentStagingWorkbook(Base):
    """Which staging profile (and version) produced a document's
    Professional Staging Workbook. Pinned when extraction runs, so a later
    profile version never silently changes how an already-processed
    document is presented or mapped. The workbook's CONTENT is not stored
    here — it is a view over the profile's own domain tables.
    """

    __tablename__ = "document_staging_workbooks"

    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_staging_workbook_document"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    profile_id: Mapped[str] = mapped_column(String(80), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)

    document_family: Mapped[str | None] = mapped_column(String(60), nullable=True)
    document_family_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Human-readable reasons the resolver chose this profile.
    resolution_reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
