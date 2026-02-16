"""Add policy settings

Revision ID: 007_policy_settings
Revises: 006_holiday_calendars
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007_policy_settings'
down_revision: Union[str, None] = '006_holiday_calendars'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'policy_settings' in sa.inspect(bind).get_table_names():
        return
    # SQLite doesn't support BOOLEAN, use INTEGER instead
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        # SQLite: use INTEGER (0/1) for boolean columns
        op.create_table(
            'policy_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('year', sa.Integer(), nullable=False),
            sa.Column('probation_months', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('cl_pl_notice_days', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('cl_pl_monthly_cap', sa.Numeric(5, 2), nullable=False, server_default='4.0'),
            sa.Column('weekly_off_day', sa.Integer(), nullable=False, server_default='7'),
            sa.Column('sandwich_enabled', sa.Integer(), nullable=False, server_default='1'),  # 1 = true
            sa.Column('sandwich_include_weekly_off', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('sandwich_include_holidays', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('sandwich_include_rh', sa.Integer(), nullable=False, server_default='0'),  # 0 = false
            sa.Column('allow_hr_override', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('year', name='uq_policy_year')
        )
    else:
        # PostgreSQL: use BOOLEAN
        op.create_table(
            'policy_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('year', sa.Integer(), nullable=False),
            sa.Column('probation_months', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('cl_pl_notice_days', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('cl_pl_monthly_cap', sa.Numeric(5, 2), nullable=False, server_default='4.0'),
            sa.Column('weekly_off_day', sa.Integer(), nullable=False, server_default='7'),
            sa.Column('sandwich_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('sandwich_include_weekly_off', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('sandwich_include_holidays', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('sandwich_include_rh', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('allow_hr_override', sa.Boolean(), nullable=False, server_default=sa.text('true')),
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
            sa.UniqueConstraint('year', name='uq_policy_year')
        )
    op.create_index(op.f('ix_policy_settings_id'), 'policy_settings', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_policy_settings_id'), table_name='policy_settings')
    op.drop_table('policy_settings')
