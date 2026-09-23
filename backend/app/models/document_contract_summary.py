from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentContractSummary(Base):
    """V3 Contract Summary sheet (docs/v3-schema-manifest.md §11) — one row
    per document. `Source File`/`Source Page`/`Evidence` are the single
    combined citation the ground-truth sheet exports; per-field provenance
    (which page/evidence backed each individual column) is kept internally
    in `field_provenance_json` only — never a V3 export column.
    """

    __tablename__ = "document_contract_summaries"

    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_contract_summary_document"),
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

    contract_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    solicitation_rfp: Mapped[str | None] = mapped_column(String(60), nullable=True)
    contract_vehicle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agency_office: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contractor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    award_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ceiling_max_aggregate: Mapped[str | None] = mapped_column(String(60), nullable=True)
    minimum_guarantee: Mapped[str | None] = mapped_column(String(60), nullable=True)
    base_period: Mapped[str | None] = mapped_column(String(80), nullable=True)
    options: Mapped[str | None] = mapped_column(String(120), nullable=True)
    max_duration: Mapped[str | None] = mapped_column(String(60), nullable=True)
    task_order_range: Mapped[str | None] = mapped_column(String(80), nullable=True)
    naics: Mapped[str | None] = mapped_column(String(10), nullable=True)
    size_standard: Mapped[str | None] = mapped_column(String(120), nullable=True)

    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    qa_status: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Internal only — per-field {page, evidence, confidence, extraction_method}.
    field_provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
