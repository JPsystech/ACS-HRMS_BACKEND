"""Add attendance logs

Revision ID: 003_attendance_logs
Revises: 002_audit_logs
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_attendance_logs'
down_revision: Union[str, None] = '002_audit_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'attendance_logs' in sa.inspect(bind).get_table_names():
        return
    # Create attendance_logs table
    # Use CURRENT_TIMESTAMP for defaults so it works on SQLite and Postgres
    op.create_table(
        'attendance_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('punch_date', sa.Date(), nullable=False),
        sa.Column('in_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('in_lat', sa.Numeric(10, 8), nullable=False),
        sa.Column('in_lng', sa.Numeric(11, 8), nullable=False),
        sa.Column('out_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('out_lat', sa.Numeric(10, 8), nullable=True),
        sa.Column('out_lng', sa.Numeric(11, 8), nullable=True),
        sa.Column('source', sa.String(), nullable=False, server_default='mobile'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id', 'punch_date', name='uq_employee_punch_date')
    )
    op.create_index(op.f('ix_attendance_logs_id'), 'attendance_logs', ['id'], unique=False)
    op.create_index(op.f('ix_attendance_logs_employee_id'), 'attendance_logs', ['employee_id'], unique=False)
    op.create_index(op.f('ix_attendance_logs_punch_date'), 'attendance_logs', ['punch_date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attendance_logs_punch_date'), table_name='attendance_logs')
    op.drop_index(op.f('ix_attendance_logs_employee_id'), table_name='attendance_logs')
    op.drop_index(op.f('ix_attendance_logs_id'), table_name='attendance_logs')
    op.drop_table('attendance_logs')
