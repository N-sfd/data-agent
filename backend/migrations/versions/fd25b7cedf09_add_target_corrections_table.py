"""add target corrections table

Revision ID: fd25b7cedf09
Revises: 14f57b4ae0bc
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fd25b7cedf09'
down_revision: Union[str, Sequence[str], None] = '14f57b4ae0bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('target_corrections',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('document_id', sa.String(length=36), nullable=False),
    sa.Column('normalized_key', sa.String(length=255), nullable=False),
    sa.Column('original_value', sa.JSON(), nullable=True),
    sa.Column('corrected_value', sa.JSON(), nullable=True),
    sa.Column('evidence_snapshot', sa.JSON(), nullable=True),
    sa.Column('changed_by', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_target_corrections_document_id'), 'target_corrections', ['document_id'], unique=False)
    op.create_index(op.f('ix_target_corrections_normalized_key'), 'target_corrections', ['normalized_key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_target_corrections_normalized_key'), table_name='target_corrections')
    op.drop_index(op.f('ix_target_corrections_document_id'), table_name='target_corrections')
    op.drop_table('target_corrections')
