"""document workspace isolation: documents.owner_workspace + staged_uploads

Revision ID: d9a3e4f5b6c7
Revises: c8f2d3e4a5b6
Create Date: 2026-09-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d9a3e4f5b6c7"
down_revision: Union[str, Sequence[str], None] = "c8f2d3e4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: the startup column patcher (ensure_documents_columns) may
    # already have added owner_workspace on a database behind this revision.
    inspector = sa.inspect(op.get_bind())
    document_columns = {c["name"] for c in inspector.get_columns("documents")}
    document_indexes = {i["name"] for i in inspector.get_indexes("documents")}
    if "owner_workspace" not in document_columns:
        op.add_column("documents", sa.Column("owner_workspace", sa.String(length=64), nullable=True))
    if "ix_documents_owner_workspace" not in document_indexes:
        op.create_index(op.f("ix_documents_owner_workspace"), "documents", ["owner_workspace"], unique=False)
    if inspector.has_table("staged_uploads"):
        return
    op.create_table(
        "staged_uploads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_workspace", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_staged_uploads_owner_workspace"), "staged_uploads", ["owner_workspace"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_staged_uploads_owner_workspace"), table_name="staged_uploads")
    op.drop_table("staged_uploads")
    op.drop_index(op.f("ix_documents_owner_workspace"), table_name="documents")
    op.drop_column("documents", "owner_workspace")
