"""Merge admin enum and profile photo heads

Revision ID: 5f43318b01b9
Revises: 0148771c3462, 024_add_admin_value_to_role_enum
Create Date: 2026-02-16 16:08:11.468146

Merges two heads:
- 0148771c3462: Add profile photo URL to employees
- 024_add_admin_value_to_role_enum: Add ADMIN value to role enum
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f43318b01b9'
down_revision: Union[str, None] = ('0148771c3462', '024_add_admin_value_to_role_enum')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
