"""Add password policy fields to employees - replaces conflicting migrations

Revision ID: 028_add_password_fields
Revises: 017_leave_wallet_balance_and_transactions
Create Date: 2026-02-25

Adds password policy fields to employees table:
- must_change_password (bool, default false)
- password_changed_at (timestamptz, nullable)
- last_login_at (timestamptz, nullable)

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = str = '028_add_password_fields'
down_revision = '017_leave_wallet_balance_and_transactions'
branch_labels = None
depends_on = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def _has_table(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


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
    if _has_column("employees", "last_login_at"):
        op.drop_column("employees", "last_login_at")
    if _has_column("employees", "password_changed_at"):
        op.drop_column("employees", "password_changed_at")
    if _has_column("employees", "must_change_password"):
        op.drop_column("employees", "must_change_password")
