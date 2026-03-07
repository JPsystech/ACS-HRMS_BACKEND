"""add description column to holidays

Revision ID: 032_add_description_to_holidays
Revises: 031_merge_heads
Create Date: 2026-03-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "032_add_description_to_holidays"
down_revision: Union[str, None] = "031_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("holidays") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("holidays") as batch_op:
        batch_op.drop_column("description")

