"""Add comp-off tables

Revision ID: 010_compoff_tables
Revises: 009_last_accrual_month
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '010_compoff_tables'
down_revision: Union[str, None] = '009_last_accrual_month'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'compoff_requests' in sa.inspect(bind).get_table_names():
        return
    # SQLite compatibility check
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Create compoff_requests table
    # Use CURRENT_TIMESTAMP for SQLite, keep now() for Postgres
    if is_sqlite:
        datetime_default = sa.text('CURRENT_TIMESTAMP')
    else:
        datetime_default = sa.text('now()')
    
    op.create_table(
        'compoff_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('worked_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='compoffrequeststatus'), nullable=False, server_default='PENDING'),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id', 'worked_date', name='uq_compoff_employee_worked_date')
    )
    op.create_index(op.f('ix_compoff_requests_id'), 'compoff_requests', ['id'], unique=False)
    op.create_index(op.f('ix_compoff_requests_employee_id'), 'compoff_requests', ['employee_id'], unique=False)
    op.create_index(op.f('ix_compoff_requests_worked_date'), 'compoff_requests', ['worked_date'], unique=False)
    
    # Create compoff_ledger table
    op.create_table(
        'compoff_ledger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('entry_type', sa.Enum('CREDIT', 'DEBIT', name='compoffledgertype'), nullable=False),
        sa.Column('days', sa.Numeric(5, 2), nullable=False),
        sa.Column('worked_date', sa.Date(), nullable=True),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('leave_request_id', sa.Integer(), nullable=True),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.ForeignKeyConstraint(['leave_request_id'], ['leave_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_compoff_ledger_id'), 'compoff_ledger', ['id'], unique=False)
    op.create_index(op.f('ix_compoff_ledger_employee_id'), 'compoff_ledger', ['employee_id'], unique=False)
    op.create_index('ix_compoff_ledger_employee_type', 'compoff_ledger', ['employee_id', 'entry_type'], unique=False)
    op.create_index('ix_compoff_ledger_employee_expires', 'compoff_ledger', ['employee_id', 'expires_on'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_compoff_ledger_employee_expires', table_name='compoff_ledger')
    op.drop_index('ix_compoff_ledger_employee_type', table_name='compoff_ledger')
    op.drop_index(op.f('ix_compoff_ledger_employee_id'), table_name='compoff_ledger')
    op.drop_index(op.f('ix_compoff_ledger_id'), table_name='compoff_ledger')
    op.drop_table('compoff_ledger')
    op.drop_index(op.f('ix_compoff_requests_worked_date'), table_name='compoff_requests')
    op.drop_index(op.f('ix_compoff_requests_employee_id'), table_name='compoff_requests')
    op.drop_index(op.f('ix_compoff_requests_id'), table_name='compoff_requests')
    op.drop_table('compoff_requests')
    op.execute('DROP TYPE compoffledgertype')
    op.execute('DROP TYPE compoffrequeststatus')
