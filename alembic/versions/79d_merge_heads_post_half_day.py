"""Merge heads after half-day support

Revision ID: 79d_merge_heads_post_half_day
Revises: 79c_add_half_day_support, a6a85711603b
Create Date: 2026-03-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '79d_merge_heads_post_half_day'
down_revision: Union[str, None] = ('79c_add_half_day_support', 'a6a85711603b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge-only revision, no schema changes
    pass


def downgrade() -> None:
    # Merge-only revision, no schema changes
    pass

