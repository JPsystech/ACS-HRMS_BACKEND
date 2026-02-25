"""Add work_mode to employees table

Revision ID: 023_add_work_mode_to_employees
Revises: 022_add_role_rank_to_roles
Create Date: 2026-02-12

This migration adds the work_mode column to employees table with default 'OFFICE'.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '023_add_work_mode_to_employees'
down_revision: Union[str, None] = '022_add_role_rank_to_roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Make migration idempotent: only add column if missing
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("employees")}
    
    if "work_mode" not in existing_cols:
        # Add work_mode column with default 'OFFICE'
        op.add_column(
            "employees",
            sa.Column("work_mode", sa.String(), nullable=False, server_default="OFFICE")
        )
        
        # Create index for better query performance
        op.create_index("ix_employees_work_mode", "employees", ["work_mode"])
    
    # Backfill existing employees to 'OFFICE' (safe to run multiple times)
    conn.execute(sa.text("UPDATE employees SET work_mode = 'OFFICE' WHERE work_mode IS NULL OR work_mode = ''"))


def downgrade() -> None:
    op.drop_index("ix_employees_work_mode", table_name="employees")
    op.drop_column("employees", "work_mode")