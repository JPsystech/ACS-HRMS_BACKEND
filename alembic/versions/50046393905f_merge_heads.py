"""merge_heads

Revision ID: 50046393905f
Revises: 028_add_birthday_wishes, 78abe87fef53
Create Date: 2026-02-25 19:41:37.638273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50046393905f'
down_revision: Union[str, None] = ('028_add_birthday_wishes', '78abe87fef53')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
