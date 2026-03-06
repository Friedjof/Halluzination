"""add filename columns to rounds

Revision ID: 8f2a91c3b4d5
Revises: 039e74b62fbd
Create Date: 2026-03-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8f2a91c3b4d5'
down_revision: Union[str, Sequence[str], None] = '039e74b62fbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rounds', sa.Column('original_filename', sa.String(500), nullable=True))
    op.add_column('rounds', sa.Column('ai_filename', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('rounds', 'ai_filename')
    op.drop_column('rounds', 'original_filename')
