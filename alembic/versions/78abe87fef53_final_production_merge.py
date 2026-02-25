"""Final production merge

Revision ID: 78abe87fef53
Revises: 1378f49191d6
Create Date: 2026-02-25 12:56:32.596598

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78abe87fef53'
down_revision: Union[str, None] = '1378f49191d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
