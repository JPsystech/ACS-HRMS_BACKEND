"""Repair: create leave_balances and leave_transactions if missing (e.g. 017 stamped but tables dropped).

Revision ID: 018_repair_wallet
Revises: 017_leave_wallet
Create Date: 2026-02-09

Run: alembic upgrade head
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "018_repair_wallet"
down_revision: Union[str, None] = "017_leave_wallet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(bind, table_name, schema="public"):
    """Check if a table exists in the database."""
    inspector = inspect(bind)
    return table_name in inspector.get_table_names(schema=schema)


def index_exists(bind, index_name, table_name, schema="public"):
    """Check if an index exists on a table."""
    inspector = inspect(bind)
    indexes = inspector.get_indexes(table_name, schema=schema)
    return any(idx["name"] == index_name for idx in indexes)


def unique_constraint_exists(bind, constraint_name, table_name, schema="public"):
    """Check if a unique constraint exists on a table."""
    inspector = inspect(bind)
    constraints = inspector.get_unique_constraints(table_name, schema=schema)
    return any(constraint["name"] == constraint_name for constraint in constraints)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "leave_balances" not in tables:
        op.create_table(
            "leave_balances",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("leave_type", sa.String(10), nullable=False),
            sa.Column("opening", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("accrued", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("used", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("remaining", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("carry_forward", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
            sa.UniqueConstraint("employee_id", "year", "leave_type", name="uq_leave_balances_employee_year_type"),
        )
        # Create indexes only if they don't already exist (idempotent)
        if not index_exists(bind, "ix_leave_balances_employee_id", "leave_balances"):
            op.create_index("ix_leave_balances_employee_id", "leave_balances", ["employee_id"], unique=False)
        if not index_exists(bind, "ix_leave_balances_year", "leave_balances"):
            op.create_index("ix_leave_balances_year", "leave_balances", ["year"], unique=False)
        
        # Check if unique constraint already exists (idempotent)
        if not unique_constraint_exists(bind, "uq_leave_balances_employee_year_type", "leave_balances"):
            op.create_unique_constraint("uq_leave_balances_employee_year_type", "leave_balances", ["employee_id", "year", "leave_type"])

    if "leave_transactions" not in tables:
        op.create_table(
            "leave_transactions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("leave_id", sa.Integer(), nullable=True),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("leave_type", sa.String(10), nullable=False),
            sa.Column("delta_days", sa.Numeric(5, 2), nullable=False),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("action_by_employee_id", sa.Integer(), nullable=True),
            sa.Column("action_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
            sa.ForeignKeyConstraint(["leave_id"], ["leave_requests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["action_by_employee_id"], ["employees.id"], ondelete="SET NULL"),
        )
        if not index_exists(bind, "ix_leave_transactions_employee_id", "leave_transactions"):
            op.create_index("ix_leave_transactions_employee_id", "leave_transactions", ["employee_id"], unique=False)
        if not index_exists(bind, "ix_leave_transactions_leave_id", "leave_transactions"):
            op.create_index("ix_leave_transactions_leave_id", "leave_transactions", ["leave_id"], unique=False)
        if not index_exists(bind, "ix_leave_transactions_year", "leave_transactions"):
            op.create_index("ix_leave_transactions_year", "leave_transactions", ["year"], unique=False)


def downgrade() -> None:
    # No-op: do not drop tables in repair migration; 017 downgrade handles that if needed.
    pass
