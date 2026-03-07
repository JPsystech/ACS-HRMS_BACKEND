"""Add notification_reminders audit table

Revision ID: 039_attendance_reminder_audit
Revises: 1378f49191d6
Create Date: 2026-03-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '039_attendance_reminder_audit'
down_revision: Union[str, None] = '1378f49191d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_reminders',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('reminder_date', sa.Date(), nullable=False),
        sa.Column('reminder_type', sa.Enum('PUNCH_IN_REMINDER', 'PUNCH_OUT_REMINDER', name='remindertype'), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.String(length=500), nullable=False),
        sa.Column('delivery_status', sa.Enum('SENT', 'FAILED', name='deliverystatus'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_reminder_unique_user_date_type', 'notification_reminders', ['user_id', 'reminder_date', 'reminder_type'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_reminder_unique_user_date_type', table_name='notification_reminders')
    op.drop_table('notification_reminders')
    # drop enums if database supports it (PostgreSQL)
    try:
        op.execute("DROP TYPE IF EXISTS remindertype")
        op.execute("DROP TYPE IF EXISTS deliverystatus")
    except Exception:
        pass

