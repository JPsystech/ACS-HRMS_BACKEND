"""Set annual_pl to 7 where currently 6 (conservative upgrade)

Revision ID: 019_pl_cap_7
Revises: 018_fl_and_accrual_ledger
Create Date: 2026-02-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '019_pl_cap_7'
down_revision: Union[str, None] = '018_fl_and_accrual_ledger'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'sqlite':
        op.execute("""
            UPDATE policy_settings
            SET annual_pl = 7
            WHERE annual_pl = 6
        """)
    else:
        op.execute("""
            UPDATE policy_settings
            SET annual_pl = 7
            WHERE annual_pl = 6
        """)


def downgrade() -> None:
    # Conservative no-op: do not downgrade policy back to 6 automatically
    pass

