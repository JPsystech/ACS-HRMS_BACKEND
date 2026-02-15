"""Add holiday calendars

Revision ID: 006_holiday_calendars
Revises: 005_paid_lwp_days
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006_holiday_calendars'
down_revision: Union[str, None] = '005_paid_lwp_days'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if 'holidays' in sa.inspect(op.get_bind()).get_table_names():
        return
    # Create holidays table
    op.create_table(
        'holidays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
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
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', 'date', name='uq_holiday_year_date')
    )
    op.create_index(op.f('ix_holidays_id'), 'holidays', ['id'], unique=False)
    op.create_index(op.f('ix_holidays_year'), 'holidays', ['year'], unique=False)
    op.create_index(op.f('ix_holidays_date'), 'holidays', ['date'], unique=False)
    
    # Create restricted_holidays table
    op.create_table(
        'restricted_holidays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
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
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', 'date', name='uq_rh_year_date')
    )
    op.create_index(op.f('ix_restricted_holidays_id'), 'restricted_holidays', ['id'], unique=False)
    op.create_index(op.f('ix_restricted_holidays_year'), 'restricted_holidays', ['year'], unique=False)
    op.create_index(op.f('ix_restricted_holidays_date'), 'restricted_holidays', ['date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_restricted_holidays_date'), table_name='restricted_holidays')
    op.drop_index(op.f('ix_restricted_holidays_year'), table_name='restricted_holidays')
    op.drop_index(op.f('ix_restricted_holidays_id'), table_name='restricted_holidays')
    op.drop_table('restricted_holidays')
    op.drop_index(op.f('ix_holidays_date'), table_name='holidays')
    op.drop_index(op.f('ix_holidays_year'), table_name='holidays')
    op.drop_index(op.f('ix_holidays_id'), table_name='holidays')
    op.drop_table('holidays')
