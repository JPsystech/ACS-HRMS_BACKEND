"""Add annual_fl to policy_settings, create leave_accrual_ledger, backfill FL balances

Revision ID: 018_fl_and_accrual_ledger
Revises: 017_leave_wallet
Create Date: 2026-02-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "018_fl_and_accrual_ledger"
down_revision: Union[str, None] = "017_leave_wallet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    # 1) Add annual_fl to policy_settings if missing
    if "policy_settings" in inspector.get_table_names():
        existing_cols = [c["name"] for c in inspector.get_columns("policy_settings")]
        if "annual_fl" not in existing_cols:
            op.add_column(
                "policy_settings",
                sa.Column("annual_fl", sa.Integer(), nullable=False, server_default="1"),
            )
            # Remove server default after backfill for Postgres
            if not is_sqlite:
                with op.get_context().autocommit_block():
                    op.execute("ALTER TABLE policy_settings ALTER COLUMN annual_fl DROP DEFAULT")

    # 2) Create leave_accrual_ledger table if missing
    if "leave_accrual_ledger" not in inspector.get_table_names():
        op.create_table(
            "leave_accrual_ledger",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),  # 1..12
            sa.Column("leave_type", sa.String(length=10), nullable=False),  # CL/SL/PL/RH/FL
            sa.Column("delta_days", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column(
                "action_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
            sa.UniqueConstraint(
                "employee_id", "year", "month", "leave_type", name="uq_accrual_emp_year_month_type"
            ),
        )
        op.create_index(
            op.f("ix_leave_accrual_ledger_employee_id"),
            "leave_accrual_ledger",
            ["employee_id"],
            unique=False,
        )
        op.create_index(
            "ix_leave_accrual_ledger_year",
            "leave_accrual_ledger",
            ["year"],
            unique=False,
        )

    # 3) Backfill FL rows in leave_balances for existing (employee_id, year)
    if "leave_balances" in inspector.get_table_names():
        # Portable INSERT .. SELECT .. WHERE NOT EXISTS for both SQLite and Postgres
        op.execute(
            """
            INSERT INTO leave_balances (employee_id, year, leave_type, opening, accrued, used, remaining, carry_forward, created_at, updated_at)
            SELECT t.employee_id, t.year, 'FL', 0, 0, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM (
                SELECT DISTINCT employee_id, year
                FROM leave_balances
            ) AS t
            WHERE NOT EXISTS (
                SELECT 1 FROM leave_balances lb
                WHERE lb.employee_id = t.employee_id
                  AND lb.year = t.year
                  AND lb.leave_type = 'FL'
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop leave_accrual_ledger
    if "leave_accrual_ledger" in inspector.get_table_names():
        op.drop_index("ix_leave_accrual_ledger_year", table_name="leave_accrual_ledger")
        op.drop_index(op.f("ix_leave_accrual_ledger_employee_id"), table_name="leave_accrual_ledger")
        op.drop_table("leave_accrual_ledger")

    # Drop annual_fl column (safe only if exists)
    if "policy_settings" in inspector.get_table_names():
        existing_cols = [c["name"] for c in inspector.get_columns("policy_settings")]
        if "annual_fl" in existing_cols:
            op.drop_column("policy_settings", "annual_fl")

