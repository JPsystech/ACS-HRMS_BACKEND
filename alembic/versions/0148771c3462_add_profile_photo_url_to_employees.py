"""add_profile_photo_url_to_employees

Revision ID: 0148771c3462
Revises: 023_add_work_mode_to_employees
Create Date: 2026-02-15 12:04:03.361585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0148771c3462'
down_revision: Union[str, None] = '023_add_work_mode_to_employees'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
