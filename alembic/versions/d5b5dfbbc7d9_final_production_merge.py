"""Final production merge

Revision ID: d5b5dfbbc7d9
Revises: 1378f49191d6
Create Date: 2026-02-25 12:50:50.973049

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5b5dfbbc7d9'
down_revision: Union[str, None] = '1378f49191d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
