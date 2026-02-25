"""empty message

Revision ID: d2800c00fafd
Revises: 018_fl_and_accrual_ledger, c6a511b65b39, dc6eaf963f24
Create Date: 2026-02-25 12:19:05.067775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2800c00fafd'
down_revision: Union[str, None] = ('018_fl_and_accrual_ledger', 'c6a511b65b39', 'dc6eaf963f24')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
