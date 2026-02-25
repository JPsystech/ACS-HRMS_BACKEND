"""Add password policy fields to employees

Revision ID: 025_add_password_fields_to_employees
Revises: 024_add_admin_value_to_role_enum
Create Date: 2026-02-21

Adds:
- must_change_password (bool, default false, not null)
- password_changed_at (timestamptz, nullable)
- last_login_at (timestamptz, nullable)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '025_add_password_fields_to_employees'
down_revision: Union[str, None] = '024_add_admin_value_to_role_enum'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("employees")}

    if "must_change_password" not in existing_cols:
        op.add_column(
            "employees",
            sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        # Normalize default for Postgres (true/false) vs SQLite (1/0)
        try:
            op.execute(sa.text("UPDATE employees SET must_change_password = 0 WHERE must_change_password IS NULL"))
        except Exception:
            pass

    if "password_changed_at" not in existing_cols:
        op.add_column(
            "employees",
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "last_login_at" not in existing_cols:
        op.add_column(
            "employees",
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("employees", "last_login_at")
    op.drop_column("employees", "password_changed_at")
    op.drop_column("employees", "must_change_password")
