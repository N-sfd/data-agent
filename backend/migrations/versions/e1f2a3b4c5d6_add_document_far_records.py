"""add document_far_records (canonical FAR model for far_part_52@1)

Revision ID: e1f2a3b4c5d6
Revises: d9a3e4f5b6c7
Create Date: 2026-09-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d9a3e4f5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_far_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("extractor_version", sa.Integer(), nullable=False),
        sa.Column("clause_key", sa.String(length=80), nullable=False),
        sa.Column("parent_clause_key", sa.String(length=80), nullable=True),
        sa.Column("basic_clause_key", sa.String(length=80), nullable=False),
        sa.Column("source_sequence_id", sa.String(length=20), nullable=False),
        sa.Column("source_order", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=30), nullable=False),
        sa.Column("load_eligible", sa.Boolean(), nullable=False),
        sa.Column("far_number", sa.String(length=40), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("heading_text", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("official_heading", sa.Text(), nullable=True),
        sa.Column("version_date", sa.String(length=40), nullable=True),
        sa.Column("clause_type", sa.String(length=20), nullable=True),
        sa.Column("prescription", sa.Text(), nullable=True),
        sa.Column("prescription_reference", sa.String(length=40), nullable=True),
        sa.Column("alternate_code", sa.String(length=30), nullable=True),
        sa.Column("alternate_heading", sa.Text(), nullable=True),
        sa.Column("alternate_instruction", sa.Text(), nullable=True),
        sa.Column("subpart", sa.String(length=40), nullable=True),
        sa.Column("subpart_title", sa.Text(), nullable=True),
        sa.Column("section_group", sa.String(length=40), nullable=True),
        sa.Column("subsection", sa.String(length=40), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("embedded_references", sa.JSON(), nullable=False),
        sa.Column("transformation_notes", sa.Text(), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "clause_key", name="uq_document_far_record_key"),
    )
    op.create_index(
        op.f("ix_document_far_records_document_id"),
        "document_far_records",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_far_records_document_id"), table_name="document_far_records")
    op.drop_table("document_far_records")
