"""Add role_rank to roles master

Revision ID: 022_add_role_rank_to_roles
Revises: 021_add_roles_table
Create Date: 2026-02-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "022_add_role_rank_to_roles"
down_revision: Union[str, None] = "021_add_roles_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  conn = op.get_bind()

  # Make migration idempotent: only add column/index if missing
  inspector = sa.inspect(conn)
  existing_cols = {col["name"] for col in inspector.get_columns("roles")}

  if "role_rank" not in existing_cols:
      op.add_column(
          "roles",
          sa.Column("role_rank", sa.Integer(), nullable=False, server_default=sa.text("99")),
      )

  existing_indexes = {idx["name"] for idx in inspector.get_indexes("roles")}
  if "ix_roles_role_rank" not in existing_indexes:
      op.create_index("ix_roles_role_rank", "roles", ["role_rank"])

  # Seed sensible ranks for existing built-in roles (safe to run multiple times)
  # Smaller rank = higher authority
  conn.execute(sa.text("UPDATE roles SET role_rank = 1 WHERE name = 'ADMIN'"))
  conn.execute(sa.text("UPDATE roles SET role_rank = 2 WHERE name = 'MD'"))
  conn.execute(sa.text("UPDATE roles SET role_rank = 3 WHERE name = 'VP'"))
  conn.execute(sa.text("UPDATE roles SET role_rank = 6 WHERE name = 'HR'"))
  conn.execute(sa.text("UPDATE roles SET role_rank = 4 WHERE name = 'MANAGER'"))
  conn.execute(sa.text("UPDATE roles SET role_rank = 5 WHERE name = 'EMPLOYEE'"))
  conn.execute(sa.text("UPDATE roles SET role_rank = 6 WHERE name = 'GUEST'"))


def downgrade() -> None:
  op.drop_index("ix_roles_role_rank", table_name="roles")
  op.drop_column("roles", "role_rank")

