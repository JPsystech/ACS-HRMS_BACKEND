"""Leave wallet: new leave_balances (per-type) and leave_transactions.

Revision ID: 017_leave_wallet
Revises: 016_attendance_naive_utc
Create Date: 2026-02-09

- Rename existing leave_balances -> leave_balances_old (backup).
- Create new leave_balances: one row per (employee_id, year, leave_type) with
  opening, accrued, used, remaining, carry_forward.
- Create leave_transactions for audit trail.
- Migrate data from leave_balances_old into new leave_balances (CL, SL, PL, RH rows).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "017_leave_wallet"
down_revision: Union[str, None] = "016_attendance_naive_utc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1) Rename existing leave_balances to leave_balances_old if it has old schema (cl_balance)
    if "leave_balances" in tables:
        cols = [c["name"] for c in inspector.get_columns("leave_balances")]
        if "cl_balance" in cols:
            op.rename_table("leave_balances", "leave_balances_old")
            tables = [t for t in tables if t != "leave_balances"] + ["leave_balances_old"]

    # 2) Create new leave_balances (re-inspect after possible rename)
    tables_now = inspector.get_table_names()
    if "leave_balances" not in tables_now:
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
        op.create_index(op.f("ix_leave_balances_employee_id"), "leave_balances", ["employee_id"], unique=False)
        op.create_index("ix_leave_balances_year", "leave_balances", ["year"], unique=False)

    # 3) Create leave_transactions
    if "leave_transactions" not in inspector.get_table_names():
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
        op.create_index(op.f("ix_leave_transactions_employee_id"), "leave_transactions", ["employee_id"], unique=False)
        op.create_index(op.f("ix_leave_transactions_leave_id"), "leave_transactions", ["leave_id"], unique=False)
        op.create_index("ix_leave_transactions_year", "leave_transactions", ["year"], unique=False)

    # 4) Data migration: leave_balances_old -> leave_balances
    if "leave_balances_old" in inspector.get_table_names():
        old_cols = [c["name"] for c in inspector.get_columns("leave_balances_old")]
        has_pl_cf = "pl_carried_forward" in old_cols
        sel = "SELECT id, employee_id, year, cl_balance, sl_balance, pl_balance, rh_used" + (", pl_carried_forward" if has_pl_cf else "") + " FROM leave_balances_old"
        result = bind.execute(text(sel))
        rows = result.fetchall()
        for row in rows:
            old_id, emp_id, yr, cl, sl, pl, rh_used = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            pl_cf = float(row[7]) if has_pl_cf and len(row) > 7 else 0.0
            cl = float(cl or 0)
            sl = float(sl or 0)
            pl = float(pl or 0)
            rh_used = int(rh_used or 0)
            for leave_type, accrued, used, carry_forward in [
                ("CL", cl, 0, 0),
                ("SL", sl, 0, 0),
                ("PL", pl, 0, pl_cf),
                ("RH", 1, min(1, rh_used), 0),
            ]:
                remaining = (accrued - used + carry_forward) if leave_type == "PL" else (accrued - used)
                bind.execute(
                    text("""
                        INSERT INTO leave_balances (employee_id, year, leave_type, opening, accrued, used, remaining, carry_forward, created_at, updated_at)
                        VALUES (:emp_id, :yr, :lt, 0, :acc, :used, :rem, :cf, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """),
                    {"emp_id": emp_id, "yr": yr, "lt": leave_type, "acc": accrued, "used": used, "rem": remaining, "cf": carry_forward if leave_type == "PL" else 0},
                )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_leave_transactions_year", table_name="leave_transactions")
    op.drop_index(op.f("ix_leave_transactions_leave_id"), table_name="leave_transactions")
    op.drop_index(op.f("ix_leave_transactions_employee_id"), table_name="leave_transactions")
    op.drop_table("leave_transactions")
    op.drop_index("ix_leave_balances_year", table_name="leave_balances")
    op.drop_index(op.f("ix_leave_balances_employee_id"), table_name="leave_balances")
    op.drop_table("leave_balances")
    if "leave_balances_old" in sa.inspect(bind).get_table_names():
        op.rename_table("leave_balances_old", "leave_balances")
