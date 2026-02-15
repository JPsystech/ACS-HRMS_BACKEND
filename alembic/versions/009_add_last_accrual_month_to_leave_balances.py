"""Add last_accrual_month to leave_balances

Revision ID: 009_last_accrual_month
Revises: 008_override_fields
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009_last_accrual_month'
down_revision: Union[str, None] = '008_override_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('leave_balances')]
    if 'last_accrual_month' in cols:
        return
    # Add last_accrual_month column to leave_balances
    op.add_column('leave_balances', sa.Column('last_accrual_month', sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column('leave_balances', 'last_accrual_month')
