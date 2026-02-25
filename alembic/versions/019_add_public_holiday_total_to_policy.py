"""Add public_holiday_total to policy_settings (ACS: 14, display only).

Revision ID: 019_public_holiday_total
Revises: 018_repair_wallet
Create Date: 2026-02-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "019_public_holiday_total"
down_revision: Union[str, None] = "018_repair_wallet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "policy_settings",
        sa.Column("public_holiday_total", sa.Integer(), nullable=True, server_default="14"),
    )


def downgrade() -> None:
    op.drop_column("policy_settings", "public_holiday_total")
