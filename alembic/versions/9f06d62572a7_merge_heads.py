"""merge_heads

Revision ID: 9f06d62572a7
Revises: 031_add_rh_description, 32c6f7f1b2a3, 7a1f3c2b9d10, a95cd944fdc6
Create Date: 2026-03-07 10:42:08.694739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f06d62572a7'
down_revision: Union[str, None] = ('031_add_rh_description', '32c6f7f1b2a3', '7a1f3c2b9d10', 'a95cd944fdc6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
