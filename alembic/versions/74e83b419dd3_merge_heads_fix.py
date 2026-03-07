"""merge heads fix

Revision ID: 74e83b419dd3
Revises: 039_attendance_reminder_audit, 9f06d62572a7
Create Date: 2026-03-07 22:35:40.681335

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74e83b419dd3'
down_revision: Union[str, None] = ('039_attendance_reminder_audit', '9f06d62572a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
