"""Merge multiple heads into a single linear head

Revision ID: 031_merge_heads
Revises: 019_pl_cap_7, 030_add_reply_to_birthday_wishes
Create Date: 2026-02-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '031_merge_heads'
down_revision: Union[str, None] = ('019_pl_cap_7', '030_add_reply_to_birthday_wishes')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge-only revision: no schema changes
    pass


def downgrade() -> None:
    # Split back into the two heads
    pass

