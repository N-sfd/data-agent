from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentClauseReference(Base):
    __tablename__ = "document_clause_references"

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

    clause_family: Mapped[str] = mapped_column(String(10), nullable=False)  # "FAR" | "DFARS" | "GSAR"

    # "listing" = Section I / incorporated-by-reference listing -> V3
    # Clauses (or DFARS) sheet. "incidental" = narrative/in-prose mention ->
    # V3 FAR References sheet. See v3-implementation-plan.md Phase 4 — one
    # table, two sheets, split by this discriminator (never by clause_family
    # alone: DFARS keeps its own sheet regardless of context per the
    # ground-truth manifest, so this column only changes FAR/GSAR routing).
    citation_context: Mapped[str] = mapped_column(
        String(12), nullable=False, default="listing"
    )

    clause_number: Mapped[str] = mapped_column(String(30), nullable=False)

    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    effective_date: Mapped[str | None] = mapped_column(String(40), nullable=True)

    alternate: Mapped[str | None] = mapped_column(String(20), nullable=True)

    deviation: Mapped[str | None] = mapped_column(String(120), nullable=True)

    variation_effective_date: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Populated only when the clause is "incorporated by full text" rather
    # than cited by reference — same row identity, not a separate family.
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    incorporation_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    qa_status: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # --- FAR References-only columns (blank for Clauses/DFARS rows) ---
    reference_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    subject_context: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contract_clause: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # --- FAR Master enrichment (far-master-schema-manifest.md) ---
    # "not_found" | "record_type_mismatch" | "title_mismatch" |
    # "date_mismatch" | "alternate_mismatch" | "matched" | "not_applicable"
    # ("not_applicable" for DFARS/GSAR, which have no master reference file).
    far_master_match_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
