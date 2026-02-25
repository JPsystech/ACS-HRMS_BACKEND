"""Repair: create leave_balances and leave_transactions if missing (e.g. 017 stamped but tables dropped).

Revision ID: 018_repair_wallet
Revises: 017_leave_wallet
Create Date: 2026-02-09

Run: alembic upgrade head
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision: str = "018_repair_wallet"
down_revision: Union[str, None] = "017_leave_wallet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(bind, table_name):
    """Check if a table exists in the database using SQLAlchemy inspector."""
    inspector = inspect(bind)
    # For SQLite, schema is None; for PostgreSQL, use default schema
    schema = None if bind.engine.name == 'sqlite' else 'public'
    return inspector.has_table(table_name, schema=schema)


def index_exists(bind, table_name, index_name):
    """Check if an index exists in the database using SQLAlchemy inspector."""
    inspector = inspect(bind)
    # For SQLite, schema is None; for PostgreSQL, use default schema
    schema = None if bind.engine.name == 'sqlite' else 'public'
    
    # Get all indexes for the table
    indexes = inspector.get_indexes(table_name, schema=schema)
    
    # Check if index exists by name
    return any(idx['name'] == index_name for idx in indexes)


def create_index_safely(bind, index_name, table_name, columns, unique=False):
    """Create an index only if it doesn't exist, works for both SQLite and PostgreSQL."""
    if not index_exists(bind, table_name, index_name):
        if bind.engine.name == 'postgresql':
            # Use PostgreSQL-specific IF NOT EXISTS syntax
            columns_str = ", ".join(columns)
            unique_str = "UNIQUE " if unique else ""
            bind.execute(
                text(f"CREATE {unique_str}INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})")
            )
        else:
            # For SQLite, we need to use direct SQL execution with IF NOT EXISTS
            # since Alembic's op.create_index doesn't support IF NOT EXISTS for SQLite
            columns_str = ", ".join(columns)
            unique_str = "UNIQUE " if unique else ""
            bind.execute(
                text(f"CREATE {unique_str}INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})")
            )


def upgrade() -> None:
    bind = op.get_bind()
    
    # ============================================
    # 1. Create leave_balances table if missing
    # ============================================
    if not table_exists(bind, "leave_balances"):
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
    
    # Create indexes for leave_balances (safe for both new and existing tables)
    create_index_safely(bind, "ix_leave_balances_employee_id", "leave_balances", ["employee_id"])
    create_index_safely(bind, "ix_leave_balances_year", "leave_balances", ["year"])

    # ============================================
    # 2. Create leave_transactions table if missing
    # ============================================
    if not table_exists(bind, "leave_transactions"):
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
    
    # Create indexes for leave_transactions (safe for both new and existing tables)
    create_index_safely(bind, "ix_leave_transactions_employee_id", "leave_transactions", ["employee_id"])
    create_index_safely(bind, "ix_leave_transactions_leave_id", "leave_transactions", ["leave_id"])
    create_index_safely(bind, "ix_leave_transactions_year", "leave_transactions", ["year"])


def downgrade() -> None:
    # No-op: do not drop tables in repair migration; 017 downgrade handles that if needed.
    pass