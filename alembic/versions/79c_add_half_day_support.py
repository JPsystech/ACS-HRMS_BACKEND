"""Add half-day support: duration and half_day_session on leave_requests

Revision ID: 79c_add_half_day_support
Revises: 78abe87fef53
Create Date: 2026-03-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '79c_add_half_day_support'
down_revision: Union[str, None] = '78abe87fef53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('leave_requests')}
    if 'duration' in cols and 'half_day_session' in cols:
        return

    if bind.dialect.name == 'sqlite':
        if 'duration' not in cols:
            op.execute("ALTER TABLE leave_requests ADD COLUMN duration TEXT DEFAULT 'FULL_DAY' NOT NULL")
        if 'half_day_session' not in cols:
            op.execute("ALTER TABLE leave_requests ADD COLUMN half_day_session TEXT NULL")
    else:
        # Create enums if not exist (PostgreSQL)
        enum_names = {e['name'] for e in insp.get_enums()}
        if 'leaveduration' not in enum_names:
            leaveduration = sa.Enum('FULL_DAY', 'HALF_DAY', name='leaveduration')
            leaveduration.create(bind, checkfirst=True)
        if 'halfdaysession' not in enum_names:
            halfdaysession = sa.Enum('FIRST_HALF', 'SECOND_HALF', name='halfdaysession')
            halfdaysession.create(bind, checkfirst=True)

        if 'duration' not in cols:
            op.add_column(
                'leave_requests',
                sa.Column('duration', sa.Enum('FULL_DAY', 'HALF_DAY', name='leaveduration'), nullable=False, server_default='FULL_DAY')
            )
        if 'half_day_session' not in cols:
            op.add_column(
                'leave_requests',
                sa.Column('half_day_session', sa.Enum('FIRST_HALF', 'SECOND_HALF', name='halfdaysession'), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        # SQLite: skip drop columns (requires table rebuild)
        return
    # PostgreSQL and others
    op.drop_column('leave_requests', 'half_day_session')
    op.drop_column('leave_requests', 'duration')
    # Drop enums
    sa.Enum(name='halfdaysession').drop(bind, checkfirst=True)
    sa.Enum(name='leaveduration').drop(bind, checkfirst=True)

