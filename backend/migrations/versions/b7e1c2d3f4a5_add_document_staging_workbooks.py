"""add document_staging_workbooks

Revision ID: b7e1c2d3f4a5
Revises: 72db43a3f638
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7e1c2d3f4a5"
down_revision: Union[str, Sequence[str], None] = "72db43a3f638"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_staging_workbooks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=80), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("document_family", sa.String(length=60), nullable=True),
        sa.Column("document_family_label", sa.String(length=120), nullable=True),
        sa.Column("resolution_reasons", sa.JSON(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_document_staging_workbook_document"),
    )
    op.create_index(
        op.f("ix_document_staging_workbooks_document_id"),
        "document_staging_workbooks",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_staging_workbooks_document_id"),
        table_name="document_staging_workbooks",
    )
    op.drop_table("document_staging_workbooks")
