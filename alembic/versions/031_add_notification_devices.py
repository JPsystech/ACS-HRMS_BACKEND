"""Add notification_devices table

Revision ID: 031_add_notification_devices
Revises: 0148771c3462
Create Date: 2026-03-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '031_add_notification_devices'
down_revision: Union[str, None] = '0148771c3462'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_devices',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('fcm_token', sa.String(length=512), nullable=False),
        sa.Column('platform', sa.String(length=32), nullable=False),
        sa.Column('app_version', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_notification_devices_user_id', 'notification_devices', ['user_id'])
    op.create_index('ix_notification_devices_fcm_token', 'notification_devices', ['fcm_token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_notification_devices_fcm_token', table_name='notification_devices')
    op.drop_index('ix_notification_devices_user_id', table_name='notification_devices')
    op.drop_table('notification_devices')

