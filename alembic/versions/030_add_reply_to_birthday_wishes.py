"""Add reply fields to birthday_wishes

Revision ID: 030_add_reply_to_birthday_wishes
Revises: 029_add_attendance_daily
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "030_add_reply_to_birthday_wishes"
down_revision = "e353b951e068"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == col for c in insp.get_columns(table))


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade():
    if _has_table("birthday_wishes"):
        if not _has_column("birthday_wishes", "reply_message"):
            op.add_column("birthday_wishes", sa.Column("reply_message", sa.Text(), nullable=True))
        if not _has_column("birthday_wishes", "replied_at"):
            op.add_column("birthday_wishes", sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if _has_table("birthday_wishes"):
        if _has_column("birthday_wishes", "replied_at"):
            op.drop_column("birthday_wishes", "replied_at")
        if _has_column("birthday_wishes", "reply_message"):
            op.drop_column("birthday_wishes", "reply_message")
