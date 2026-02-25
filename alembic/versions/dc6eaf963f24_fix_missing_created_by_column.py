"""fix_missing_created_by_column

Revision ID: dc6eaf963f24
Revises: 027_culture_enhancements
Create Date: 2026-02-21 16:41:52.835051

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc6eaf963f24'
down_revision: Union[str, None] = '027_culture_enhancements'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    # Add created_by column if it doesn't exist
    if _has_table("birthday_greetings") and not _has_column("birthday_greetings", "created_by"):
        op.add_column("birthday_greetings", sa.Column("created_by", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_birthday_greetings_created_by_employees",
            "birthday_greetings",
            "employees",
            ["created_by"],
            ["id"],
        )


def downgrade() -> None:
    # Remove created_by column if it exists
    if _has_table("birthday_greetings") and _has_column("birthday_greetings", "created_by"):
        op.drop_constraint("fk_birthday_greetings_created_by_employees", "birthday_greetings", type_="foreignkey")
        op.drop_column("birthday_greetings", "created_by")
