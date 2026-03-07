"""Add image_key to holidays and restricted_holidays

Revision ID: 030_add_holiday_image_key
Revises: 029_add_photo_key
Create Date: 2026-03-05
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '030_add_holiday_image_key'
down_revision: Union[str, None] = '029_add_photo_key'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _has_column("holidays", "image_key"):
        op.add_column("holidays", sa.Column("image_key", sa.Text(), nullable=True))
    if not _has_column("restricted_holidays", "image_key"):
        op.add_column("restricted_holidays", sa.Column("image_key", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("restricted_holidays", "image_key"):
        op.drop_column("restricted_holidays", "image_key")
    if _has_column("holidays", "image_key"):
        op.drop_column("holidays", "image_key")

