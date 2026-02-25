from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "027_culture_enhancements"
down_revision: Union[str, None] = "026_culture_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if _has_table("employees") and not _has_column("employees", "profile_photo_updated_at"):
        op.add_column("employees", sa.Column("profile_photo_updated_at", sa.DateTime(timezone=True), nullable=True))
    if _has_table("birthday_greetings"):
        if not _has_column("birthday_greetings", "greeting_message"):
            op.add_column("birthday_greetings", sa.Column("greeting_message", sa.Text(), nullable=True))
        if not _has_column("birthday_greetings", "created_by"):
            op.add_column("birthday_greetings", sa.Column("created_by", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_birthday_greetings_created_by_employees",
                "birthday_greetings",
                "employees",
                ["created_by"],
                ["id"],
            )
    else:
        op.create_table(
            "birthday_greetings",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False, index=True),
            sa.Column("date", sa.Date(), nullable=False, index=True),
            sa.Column("greeting_image_url", sa.Text(), nullable=True),
            sa.Column("greeting_message", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("wish_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("wish_sent_by", sa.Integer(), nullable=True),
            sa.Column("wish_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
            sa.ForeignKeyConstraint(["wish_sent_by"], ["employees.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["employees.id"]),
        )
        op.create_unique_constraint("uq_birthday_employee_date", "birthday_greetings", ["employee_id", "date"])


def downgrade() -> None:
    if _has_table("birthday_greetings"):
        if _has_column("birthday_greetings", "created_by"):
            op.drop_constraint("fk_birthday_greetings_created_by_employees", "birthday_greetings", type_="foreignkey")
            op.drop_column("birthday_greetings", "created_by")
        if _has_column("birthday_greetings", "greeting_message"):
            op.drop_column("birthday_greetings", "greeting_message")
    if _has_table("employees") and _has_column("employees", "profile_photo_updated_at"):
        op.drop_column("employees", "profile_photo_updated_at")
