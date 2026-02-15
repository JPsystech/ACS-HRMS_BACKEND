"""Merge multiple heads (013_attendance_sessions and 8d7b50ba54c3)

Revision ID: 014_merge_heads
Revises: 013_attendance_sessions, 8d7b50ba54c3
Create Date: 2026-02-06

Resolves "Multiple head revisions" so that alembic upgrade head runs a single chain.
"""
from typing import Sequence, Tuple, Union
from alembic import op

revision: str = "014_merge_heads"
down_revision: Union[str, Tuple[str, ...], None] = ("013_attendance_sessions", "8d7b50ba54c3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
