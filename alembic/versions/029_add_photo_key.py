"""Add photo_key column to employees table

Revision ID: 029_add_photo_key
Revises: 78abe87fef53
Create Date: 2026-02-28

Adds photo_key column to store R2 object key for profile photos
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '029_add_photo_key'
down_revision: Union[str, None] = '78abe87fef53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _has_column("employees", "photo_key"):
        op.add_column("employees", sa.Column("photo_key", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("employees", "photo_key"):
        op.drop_column("employees", "photo_key")
