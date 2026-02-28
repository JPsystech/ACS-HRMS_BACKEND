"""Merge all heads including photo_key

Revision ID: a6a85711603b
Revises: 029_add_photo_key, 031_merge_heads
Create Date: 2026-02-28 10:46:39.441022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6a85711603b'
down_revision: Union[str, None] = ('029_add_photo_key', '031_merge_heads')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
