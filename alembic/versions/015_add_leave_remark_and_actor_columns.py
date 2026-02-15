"""Add leave approved/rejected/cancelled remark and actor columns

Revision ID: 015_leave_remarks
Revises: 014_merge_heads
Create Date: 2026-02-06

Persist remarks and actor IDs/timestamps for approve, reject, and cancel
so Admin and Flutter can display them.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "015_leave_remarks"
down_revision: Union[str, None] = "014_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("leave_requests")]
    is_sqlite = bind.dialect.name == "sqlite"

    def add_col(name: str, col_def):
        if name not in cols:
            op.add_column("leave_requests", col_def)

    add_col("approved_remark", sa.Column("approved_remark", sa.Text(), nullable=True))
    add_col("approved_at", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    add_col("rejected_remark", sa.Column("rejected_remark", sa.Text(), nullable=True))
    # SQLite cannot add FK in ALTER TABLE; add Integer only (relationship still enforced by app)
    add_col(
        "rejected_by_id",
        sa.Column("rejected_by_id", sa.Integer(), nullable=True)
        if is_sqlite
        else sa.Column("rejected_by_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
    )
    add_col("rejected_at", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    add_col("cancelled_remark", sa.Column("cancelled_remark", sa.Text(), nullable=True))
    add_col(
        "cancelled_by_id",
        sa.Column("cancelled_by_id", sa.Integer(), nullable=True)
        if is_sqlite
        else sa.Column("cancelled_by_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
    )
    add_col("cancelled_at", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))

    # Indexes for FK columns (only when column was just added)
    if "rejected_by_id" not in cols:
        op.create_index(op.f("ix_leave_requests_rejected_by_id"), "leave_requests", ["rejected_by_id"], unique=False)
    if "cancelled_by_id" not in cols:
        op.create_index(op.f("ix_leave_requests_cancelled_by_id"), "leave_requests", ["cancelled_by_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leave_requests_cancelled_by_id"), table_name="leave_requests", if_exists=True)
    op.drop_index(op.f("ix_leave_requests_rejected_by_id"), table_name="leave_requests", if_exists=True)
    op.drop_column("leave_requests", "cancelled_at")
    op.drop_column("leave_requests", "cancelled_by_id")
    op.drop_column("leave_requests", "cancelled_remark")
    op.drop_column("leave_requests", "rejected_at")
    op.drop_column("leave_requests", "rejected_by_id")
    op.drop_column("leave_requests", "rejected_remark")
    op.drop_column("leave_requests", "approved_at")
    op.drop_column("leave_requests", "approved_remark")
