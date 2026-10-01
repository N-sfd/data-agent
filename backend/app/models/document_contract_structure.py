from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentContractStructure(Base):
    """The source-adaptive contract structure of one document (cover-form
    fields, schedule tables, clauses with incorporation context), built once
    from the PDF layout by app.contract_structure and read by the contract
    staging profile. Independent of the V3 tables."""

    __tablename__ = "document_contract_structures"

    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_contract_structure_document"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extractor_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
