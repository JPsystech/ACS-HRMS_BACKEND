"""Add override fields to leave_requests

Revision ID: 008_override_fields
Revises: 007_policy_settings
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '008_override_fields'
down_revision: Union[str, None] = '007_policy_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('leave_requests')]
    if 'override_policy' in cols:
        return
    # Add override fields to leave_requests
    op.add_column('leave_requests', sa.Column('override_policy', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('leave_requests', sa.Column('override_remark', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('leave_requests', 'override_remark')
    op.drop_column('leave_requests', 'override_policy')
