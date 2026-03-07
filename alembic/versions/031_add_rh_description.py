"""Add description to restricted_holidays

Revision ID: 031_add_rh_description
Revises: 030_add_holiday_image_key
Create Date: 2026-03-05
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '031_add_rh_description'
down_revision: Union[str, None] = '030_add_holiday_image_key'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _has_column("restricted_holidays", "description"):
        op.add_column("restricted_holidays", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("restricted_holidays", "description"):
        op.drop_column("restricted_holidays", "description")

