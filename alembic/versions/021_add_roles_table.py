"""Add roles master table for WFH enablement

Revision ID: 021_add_roles_table
Revises: 020_employee_mobile
Create Date: 2026-02-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "021_add_roles_table"
down_revision: Union[str, None] = "020_employee_mobile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create roles table
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("wfh_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_roles_id", "roles", ["id"])
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    # Seed default roles matching existing enum values
    roles_table = sa.table(
        "roles",
        sa.column("name", sa.String),
        sa.column("wfh_enabled", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        roles_table,
        [
            {"name": "EMPLOYEE", "wfh_enabled": False, "is_active": True},
            {"name": "MANAGER", "wfh_enabled": False, "is_active": True},
            {"name": "HR", "wfh_enabled": False, "is_active": True},
            {"name": "MD", "wfh_enabled": False, "is_active": True},
            {"name": "ADMIN", "wfh_enabled": False, "is_active": True},
            {"name": "VP", "wfh_enabled": False, "is_active": True},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_index("ix_roles_id", table_name="roles")
    op.drop_table("roles")

