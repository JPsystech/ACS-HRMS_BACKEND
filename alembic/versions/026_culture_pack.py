from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "026_culture_pack"
down_revision: Union[str, None] = "025_combined_pwd_culture"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def _has_table(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if _has_table("employees"):
        if not _has_column("employees", "dob"):
            op.add_column("employees", sa.Column("dob", sa.Date(), nullable=True))
        if not _has_column("employees", "profile_photo_url"):
            op.add_column("employees", sa.Column("profile_photo_url", sa.Text(), nullable=True))
    if not _has_table("birthday_greetings"):
        op.create_table(
            "birthday_greetings",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False, index=True),
            sa.Column("date", sa.Date(), nullable=False, index=True),
            sa.Column("greeting_image_url", sa.Text(), nullable=True),
            sa.Column("wish_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("wish_sent_by", sa.Integer(), nullable=True),
            sa.Column("wish_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
            sa.ForeignKeyConstraint(["wish_sent_by"], ["employees.id"]),
        )
        op.create_unique_constraint("uq_birthday_employee_date", "birthday_greetings", ["employee_id", "date"])


def downgrade() -> None:
    if _has_table("birthday_greetings"):
        op.drop_constraint("uq_birthday_employee_date", "birthday_greetings", type_="unique")
        op.drop_table("birthday_greetings")
    if _has_table("employees"):
        if _has_column("employees", "profile_photo_url"):
            op.drop_column("employees", "profile_photo_url")
        if _has_column("employees", "dob"):
            op.drop_column("employees", "dob")
