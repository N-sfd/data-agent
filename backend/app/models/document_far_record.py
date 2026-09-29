from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DocumentFarRecord(Base):
    """One row of the canonical FAR model for a FAR regulation source
    (far_part_52@1): a section / provision / clause, a Subpart heading, a
    reserved record, or a structural Alternate linked to its basic clause.

    System-neutral: nothing here is an Oracle field. Keys are deterministic
    (FAR-52.204-3, FAR-Subpart_52.1, FAR-52.215-1-ALT-I) so re-runs and
    later adapters see the same identities. Structural and reserved records
    are kept (load_eligible False), never discarded. Text is stored exactly
    as extracted — validation flags, it never rewrites.
    """

    __tablename__ = "document_far_records"

    __table_args__ = (
        UniqueConstraint("document_id", "clause_key", name="uq_document_far_record_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extractor_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Canonical identity and routing.
    clause_key: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_clause_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    basic_clause_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_sequence_id: Mapped[str] = mapped_column(String(20), nullable=False)
    source_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    load_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # FAR identity and headings.
    far_number: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    heading_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    clause_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Prescription ("As prescribed in ...") and alternate variant data.
    prescription: Mapped[str | None] = mapped_column(Text, nullable=True)
    prescription_reference: Mapped[str | None] = mapped_column(String(40), nullable=True)
    alternate_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    alternate_heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternate_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hierarchy (Subpart → section group → record).
    subpart: Mapped[str | None] = mapped_column(String(40), nullable=True)
    subpart_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_group: Mapped[str | None] = mapped_column(String(40), nullable=True)
    subsection: Mapped[str | None] = mapped_column(String(40), nullable=True)

    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedded_references: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    transformation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source locators (DOM path, element id, heading trail, and the DOM
    # paths of the heading / official heading / prescription elements).
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Extraction findings that make the record Needs Review.
    issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
