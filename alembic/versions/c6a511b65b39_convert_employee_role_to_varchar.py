"""convert_employee_role_to_varchar

Revision ID: c6a511b65b39
Revises: 5f43318b01b9
Create Date: 2026-02-16 16:19:59.707771

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6a511b65b39'
down_revision: Union[str, None] = '5f43318b01b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get the database bind
    bind = op.get_bind()
    
    # Check if we're using PostgreSQL
    if bind.engine.name == 'postgresql':
        # Convert employees.role from enum to varchar
        op.execute(
            "ALTER TABLE employees ALTER COLUMN role TYPE VARCHAR USING role::text"
        )
        
        # Optional: Drop the enum type if it's no longer used
        # Check if the enum type exists and is not used by any other table
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type t
                    JOIN pg_attribute a ON t.oid = a.atttypid
                    JOIN pg_class c ON a.attrelid = c.oid
                    WHERE t.typname = 'role' AND c.relname != 'employees'
                ) THEN
                    DROP TYPE role;
                END IF;
            END$$;
        """)
    else:
        # For SQLite, no conversion needed as it already stores enums as text
        pass


def downgrade() -> None:
    bind = op.get_bind()
    
    if bind.engine.name == 'postgresql':
        # Recreate the enum type
        op.execute("CREATE TYPE role AS ENUM ('ADMIN', 'HR', 'EMPLOYEE', 'MANAGER')")
        
        # Convert back to enum
        op.execute("""
            ALTER TABLE employees ALTER COLUMN role TYPE role USING role::role
        """)
    else:
        # SQLite doesn't need downgrade as it stores as text
        pass
