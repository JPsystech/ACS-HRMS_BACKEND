"""merge_heads_after_holiday_desc

Revision ID: a95cd944fdc6
Revises: 032_add_description_to_holidays, 79d_merge_heads_post_half_day
Create Date: 2026-03-03 15:45:19.720835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a95cd944fdc6'
down_revision: Union[str, None] = ('032_add_description_to_holidays', '79d_merge_heads_post_half_day')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
