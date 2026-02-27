from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "025_add_password_fields_to_employees"
down_revision: Union[str, None] = "024_add_admin_value_to_role_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _has_column("employees", "must_change_password"):
        op.add_column(
            "employees",
            sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        try:
            op.execute(sa.text("UPDATE employees SET must_change_password = false WHERE must_change_password IS NULL"))
        except Exception:
            pass
    if not _has_column("employees", "password_changed_at"):
        op.add_column(
            "employees",
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column("employees", "last_login_at"):
        op.add_column(
            "employees",
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    if _has_column("employees", "last_login_at"):
        op.drop_column("employees", "last_login_at")
    if _has_column("employees", "password_changed_at"):
        op.drop_column("employees", "password_changed_at")
    if _has_column("employees", "must_change_password"):
        op.drop_column("employees", "must_change_password")
