"""Add ADMIN value to role enum

Revision ID: 024_add_admin_value_to_role_enum
Revises: 023_add_work_mode_to_employees
Create Date: 2026-02-16
"""
from typing import Sequence, Union

from alembic import op


revision: str = "024_add_admin_value_to_role_enum"
down_revision: Union[str, None] = "023_add_work_mode_to_employees"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely add 'ADMIN' value to the role enum if it doesn't exist
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


def downgrade() -> None:
    # Note: Removing enum values is complex and not typically done in downgrade
    # The enum value will remain in the database but won't be used by the application
    pass