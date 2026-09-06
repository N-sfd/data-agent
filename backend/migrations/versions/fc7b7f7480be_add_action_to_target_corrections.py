"""add action column to target_corrections

Revision ID: fc7b7f7480be
Revises: fd25b7cedf09
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fc7b7f7480be'
down_revision: Union[str, Sequence[str], None] = 'fd25b7cedf09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'target_corrections',
        sa.Column(
            'action',
            sa.String(length=20),
            nullable=False,
            server_default='edit',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('target_corrections', 'action')
