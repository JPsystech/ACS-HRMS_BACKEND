"""Add paid_days and lwp_days to leave_requests

Revision ID: 005_paid_lwp_days
Revises: 004_leave_tables
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_paid_lwp_days'
down_revision: Union[str, None] = '004_leave_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c['name'] for c in sa.inspect(bind).get_columns('leave_requests')]
    if 'paid_days' in cols:
        return
    # Add paid_days and lwp_days columns to leave_requests
    if bind.dialect.name == 'sqlite':
        # SQLite doesn't support ALTER COLUMN ADD, so we need to recreate table
        # For SQLite, we'll add columns using ALTER TABLE ADD COLUMN (SQLite 3.1.3+)
        op.execute("ALTER TABLE leave_requests ADD COLUMN paid_days NUMERIC(5, 2) DEFAULT 0 NOT NULL")
        op.execute("ALTER TABLE leave_requests ADD COLUMN lwp_days NUMERIC(5, 2) DEFAULT 0 NOT NULL")
    else:
        # PostgreSQL and other databases
        op.add_column('leave_requests',
            sa.Column('paid_days', sa.Numeric(5, 2), nullable=False, server_default='0')
        )
        op.add_column('leave_requests',
            sa.Column('lwp_days', sa.Numeric(5, 2), nullable=False, server_default='0')
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        # SQLite doesn't support DROP COLUMN directly
        # Would need to recreate table, but for downgrade we'll skip
        pass
    else:
        op.drop_column('leave_requests', 'lwp_days')
        op.drop_column('leave_requests', 'paid_days')
