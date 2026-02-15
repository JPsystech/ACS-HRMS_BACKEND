"""Add attendance_sessions and attendance_events tables

Revision ID: 013_attendance_sessions
Revises: 012_approver_id
Create Date: 2026-02-06

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "013_attendance_sessions"
down_revision: Union[str, None] = "012_approver_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    ts_default = sa.text("CURRENT_TIMESTAMP") if is_sqlite else sa.text("now()")

    op.create_table(
        "attendance_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("punch_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("punch_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
        sa.Column("punch_in_source", sa.String(), nullable=False, server_default="WEB"),
        sa.Column("punch_out_source", sa.String(), nullable=True),
        sa.Column("punch_in_ip", sa.String(), nullable=True),
        sa.Column("punch_out_ip", sa.String(), nullable=True),
        sa.Column("punch_in_device_id", sa.String(), nullable=True),
        sa.Column("punch_out_device_id", sa.String(), nullable=True),
        sa.Column("punch_in_geo", sa.JSON(), nullable=True),
        sa.Column("punch_out_geo", sa.JSON(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "work_date", name="uq_attendance_sessions_employee_work_date"),
    )
    op.create_index(op.f("ix_attendance_sessions_id"), "attendance_sessions", ["id"], unique=False)
    op.create_index(op.f("ix_attendance_sessions_employee_id"), "attendance_sessions", ["employee_id"], unique=False)
    op.create_index(op.f("ix_attendance_sessions_work_date"), "attendance_sessions", ["work_date"], unique=False)

    op.create_table(
        "attendance_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["attendance_sessions.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attendance_events_id"), "attendance_events", ["id"], unique=False)
    op.create_index(op.f("ix_attendance_events_session_id"), "attendance_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_attendance_events_employee_id"), "attendance_events", ["employee_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_attendance_events_employee_id"), table_name="attendance_events")
    op.drop_index(op.f("ix_attendance_events_session_id"), table_name="attendance_events")
    op.drop_index(op.f("ix_attendance_events_id"), table_name="attendance_events")
    op.drop_table("attendance_events")
    op.drop_index(op.f("ix_attendance_sessions_work_date"), table_name="attendance_sessions")
    op.drop_index(op.f("ix_attendance_sessions_employee_id"), table_name="attendance_sessions")
    op.drop_index(op.f("ix_attendance_sessions_id"), table_name="attendance_sessions")
    op.drop_table("attendance_sessions")
