"""Add ADMIN value to role enum

Revision ID: 024_add_admin_value_to_role_enum
Revises: 023_add_work_mode_to_employees
Create Date: 2026-02-16
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text


revision: str = "024_add_admin_value_to_role_enum"
down_revision: Union[str, None] = "023_add_work_mode_to_employees"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    
    # Check database type
    is_postgresql = bind.engine.name == 'postgresql'
    
    if is_postgresql:
        # PostgreSQL: Safely add 'ADMIN' value to the role enum if it doesn't exist
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM pg_type t 
                JOIN pg_enum e ON t.oid = e.enumtypid 
                WHERE t.typname = 'role' AND e.enumlabel = 'ADMIN'
            ) THEN
                ALTER TYPE role ADD VALUE 'ADMIN';
            END IF;
        END$$;
        """)
    else:
        # SQLite: No-op since SQLite doesn't have native enum types
        # The role column is VARCHAR in SQLite, so 'ADMIN' can be inserted directly
        # Check if we need to update any existing constraints, but typically not needed
        pass


def downgrade() -> None:
    # Note: Removing enum values is complex and not typically done in downgrade
    # The enum value will remain in the database but won't be used by the application
    # For SQLite: No action needed since it's just VARCHAR
    pass