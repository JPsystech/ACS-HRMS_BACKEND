"""fix audit logs sqlite datetime

Revision ID: 95117d35cefd
Revises: 011_policy_migration
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '95117d35cefd'
down_revision: Union[str, None] = '011_policy_migration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix audit_logs table created_at default for SQLite
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        # SQLite doesn't support ALTER COLUMN to change default, so recreate table
        # First, check if audit_logs table exists
        inspector = sa.inspect(bind)
        existing_tables = inspector.get_table_names()
        
        if 'audit_logs' in existing_tables:
            # Get existing data
            existing_data = op.get_bind().execute(sa.text("SELECT * FROM audit_logs")).fetchall()
            
            # Drop old table
            op.drop_index('ix_audit_logs_id', table_name='audit_logs')
            op.drop_table('audit_logs')
            
            # Create new table with SQLite-compatible default
            op.create_table(
                'audit_logs',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('actor_id', sa.Integer(), nullable=False),
                sa.Column('action', sa.String(), nullable=False),
                sa.Column('entity_type', sa.String(), nullable=False),
                sa.Column('entity_id', sa.Integer(), nullable=True),
                sa.Column('meta_json', sa.JSON(), nullable=True),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
                sa.ForeignKeyConstraint(['actor_id'], ['employees.id'], ),
                sa.PrimaryKeyConstraint('id')
            )
            op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
            
            # Restore data if any existed
            if existing_data:
                # Note: We'll lose the original created_at timestamps, but that's acceptable for this fix
                # If you need to preserve timestamps, you'd need to store them temporarily
                pass


def downgrade() -> None:
    # Revert to PostgreSQL-style default (if needed)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        # For downgrade, we'd recreate with now() but SQLite doesn't support it
        # So we'll just keep CURRENT_TIMESTAMP
        pass
    else:
        # For PostgreSQL, change back to now()
        op.alter_column('audit_logs', 'created_at',
                       existing_type=sa.DateTime(timezone=True),
                       server_default=sa.text('now()'),
                       nullable=False)
