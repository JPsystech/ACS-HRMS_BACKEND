"""Add leave tables

Revision ID: 004_leave_tables
Revises: 003_attendance_logs
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_leave_tables'
down_revision: Union[str, None] = '003_attendance_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if 'leave_requests' in sa.inspect(op.get_bind()).get_table_names():
        return
    # Create leave_requests table
    op.create_table(
        'leave_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('leave_type', sa.Enum('CL', 'PL', 'SL', 'RH', 'COMPOFF', 'LWP', name='leavetype'), nullable=False),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', name='leavestatus'), nullable=False, server_default='PENDING'),
        sa.Column('computed_days', sa.Numeric(5, 2), nullable=False),
        sa.Column('computed_days_by_month', sa.String(), nullable=True),
        sa.Column(
            'applied_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
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
        sa.CheckConstraint('from_date <= to_date', name='check_from_date_le_to_date')
    )
    op.create_index(op.f('ix_leave_requests_id'), 'leave_requests', ['id'], unique=False)
    op.create_index(op.f('ix_leave_requests_employee_id'), 'leave_requests', ['employee_id'], unique=False)
    op.create_index('ix_leave_requests_employee_dates', 'leave_requests', ['employee_id', 'from_date', 'to_date'], unique=False)
    
    # Create leave_approvals table
    op.create_table(
        'leave_approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('leave_request_id', sa.Integer(), nullable=False),
        sa.Column('action_by', sa.Integer(), nullable=False),
        sa.Column('action', sa.Enum('APPROVE', 'REJECT', 'CANCEL', name='approvalaction'), nullable=False),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column(
            'action_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['leave_request_id'], ['leave_requests.id'], ),
        sa.ForeignKeyConstraint(['action_by'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_leave_approvals_id'), 'leave_approvals', ['id'], unique=False)
    op.create_index(op.f('ix_leave_approvals_leave_request_id'), 'leave_approvals', ['leave_request_id'], unique=False)
    
    # Create leave_balances table
    op.create_table(
        'leave_balances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('cl_balance', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('sl_balance', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('pl_balance', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('rh_used', sa.Integer(), nullable=False, server_default='0'),
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
        sa.UniqueConstraint('employee_id', 'year', name='uq_employee_year')
    )
    op.create_index(op.f('ix_leave_balances_id'), 'leave_balances', ['id'], unique=False)
    op.create_index(op.f('ix_leave_balances_employee_id'), 'leave_balances', ['employee_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_leave_balances_employee_id'), table_name='leave_balances')
    op.drop_index(op.f('ix_leave_balances_id'), table_name='leave_balances')
    op.drop_table('leave_balances')
    op.drop_index(op.f('ix_leave_approvals_leave_request_id'), table_name='leave_approvals')
    op.drop_index(op.f('ix_leave_approvals_id'), table_name='leave_approvals')
    op.drop_table('leave_approvals')
    op.drop_index('ix_leave_requests_employee_dates', table_name='leave_requests')
    op.drop_index(op.f('ix_leave_requests_employee_id'), table_name='leave_requests')
    op.drop_index(op.f('ix_leave_requests_id'), table_name='leave_requests')
    op.drop_table('leave_requests')
    op.execute('DROP TYPE approvalaction')
    op.execute('DROP TYPE leavestatus')
    op.execute('DROP TYPE leavetype')
