"""add attendance_daily summary table

Revision ID: 029_add_attendance_daily
Revises: 028_add_birthday_wishes
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "029_add_attendance_daily"
down_revision = "028_add_birthday_wishes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "attendance_daily",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("first_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_good", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint("user_id", "work_date", name="pk_attendance_daily"),
    )
    op.create_index("ix_attendance_daily_user_date", "attendance_daily", ["user_id", "work_date"])


def downgrade():
    op.drop_index("ix_attendance_daily_user_date", table_name="attendance_daily")
    op.drop_table("attendance_daily")

