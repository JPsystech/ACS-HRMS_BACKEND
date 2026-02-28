"""Create_thoughts_table

Revision ID: 88e15c5eeb9c
Revises: a6a85711603b
Create Date: 2026-02-28 17:05:06.516820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88e15c5eeb9c'
down_revision: Union[str, None] = 'a6a85711603b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
