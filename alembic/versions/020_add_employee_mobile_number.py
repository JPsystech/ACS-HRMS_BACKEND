"""Add mobile_number to employees.

Revision ID: 020_employee_mobile
Revises: 019_public_holiday_total
Create Date: 2026-02-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "020_employee_mobile"
down_revision: Union[str, None] = "019_public_holiday_total"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("mobile_number", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employees", "mobile_number")
