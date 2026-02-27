"""merge_heads_for_birthday_and_attendance

Revision ID: e353b951e068
Revises: 029_add_attendance_daily, 50046393905f
Create Date: 2026-02-27 11:18:16.966226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e353b951e068'
down_revision: Union[str, None] = ('029_add_attendance_daily', '50046393905f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
