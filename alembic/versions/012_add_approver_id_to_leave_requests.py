"""Add approver_id to leave_requests table

Revision ID: 012_approver_id
Revises: 011_policy_migration
Create Date: 2026-02-06

This migration adds the approver_id column to leave_requests table for reporting manager-based leave approval routing.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '012_approver_id'
down_revision: Union[str, None] = '011_policy_migration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Check if column already exists (for partial migration recovery)
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('leave_requests')]
    
    if 'approver_id' not in existing_columns:
        # Add approver_id column with foreign key constraint
        if is_sqlite:
            # SQLite doesn't support adding foreign key constraints with ALTER TABLE
            # We'll add the column first, then create the foreign key separately if needed
            op.add_column('leave_requests', sa.Column('approver_id', sa.Integer(), nullable=True))
            # For SQLite, we'll rely on application-level foreign key enforcement
        else:
            # For PostgreSQL, add column with proper foreign key constraint
            op.add_column('leave_requests', sa.Column('approver_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True))
        
        # Create index for better query performance
        op.create_index(op.f('ix_leave_requests_approver_id'), 'leave_requests', ['approver_id'])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Check if column exists before trying to remove it
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('leave_requests')]
    
    if 'approver_id' in existing_columns:
        # Drop index first
        op.drop_index(op.f('ix_leave_requests_approver_id'), 'leave_requests')
        
        # Drop column
        op.drop_column('leave_requests', 'approver_id')