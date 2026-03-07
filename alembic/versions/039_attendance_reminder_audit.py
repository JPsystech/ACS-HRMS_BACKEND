"""attendance_reminder_audit dummy

Revision ID: 039_attendance_reminder_audit
Revises: 032_add_description_to_holidays
Create Date: 2026-03-07

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '039_attendance_reminder_audit'
down_revision: Union[str, None] = '032_add_description_to_holidays'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
