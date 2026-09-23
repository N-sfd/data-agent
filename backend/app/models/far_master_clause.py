from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FarMasterClause(Base):
    """Read-only reference data ingested once from
    reference/schemas/part_52_FAR_Master_FINAL.xlsx (docs/far-master-schema-
    manifest.md). Join key is `far_number` (bare dotted number, e.g.
    "52.204-21") — never the contract's "FAR 52.204-21"-prefixed text.

    Used only to VALIDATE/ENRICH a clause candidate that contract evidence
    already established — never to determine that a clause exists in a
    contract (far-master-schema-manifest.md's governing rule).
    """

    __tablename__ = "far_master_clauses"

    far_number: Mapped[str] = mapped_column(String(20), primary_key=True)

    far_record_id: Mapped[str] = mapped_column(String(30), nullable=False)

    official_display_title: Mapped[str] = mapped_column(String(400), nullable=False)

    # "Clause" | "Reserved" | "Provision" | "Instruction / Scope / Section"
    record_type: Mapped[str] = mapped_column(String(40), nullable=False)

    effective_date: Mapped[str | None] = mapped_column(String(40), nullable=True)

    prescribed_in: Mapped[str | None] = mapped_column(String(60), nullable=True)

    has_alternates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    clause_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
