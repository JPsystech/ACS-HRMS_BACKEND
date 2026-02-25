"""Combined password fields and culture pack - resolves overlap

Revision ID: 025_combined_password_and_culture
Revises: 024_add_admin_value_to_role_enum
Create Date: 2026-02-25

Combines:
- Password policy fields (must_change_password, password_changed_at, last_login_at)
- Culture pack features (dob, profile_photo_url, birthday_greetings table)

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '025_combined_password_and_culture'
down_revision: Union[str, None] = '024_add_admin_value_to_role_enum'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def _has_table(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("employees")}

    # Add password policy fields
    if "must_change_password" not in existing_cols:
        op.add_column(
            "employees",
            sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        # Normalize default for Postgres (true/false) vs SQLite (1/0)
        try:
            op.execute(sa.text("UPDATE employees SET must_change_password = false WHERE must_change_password IS NULL"))
        except Exception:
            pass

    if "password_changed_at" not in existing_cols:
        op.add_column(
            "employees",
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "last_login_at" not in existing_cols:
        op.add_column(
            "employees",
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        )

    # Add culture pack fields
    if "dob" not in existing_cols:
        op.add_column("employees", sa.Column("dob", sa.Date(), nullable=True))
    
    if "profile_photo_url" not in existing_cols:
        op.add_column("employees", sa.Column("profile_photo_url", sa.Text(), nullable=True))

    # Create birthday_greetings table
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
    # Remove birthday greetings table
    if _has_table("birthday_greetings"):
        op.drop_constraint("uq_birthday_employee_date", "birthday_greetings", type_="unique")
        op.drop_table("birthday_greetings")
    
    # Remove culture pack fields
    if _has_column("employees", "profile_photo_url"):
        op.drop_column("employees", "profile_photo_url")
    if _has_column("employees", "dob"):
        op.drop_column("employees", "dob")
    
    # Remove password fields
    if _has_column("employees", "last_login_at"):
        op.drop_column("employees", "last_login_at")
    if _has_column("employees", "password_changed_at"):
        op.drop_column("employees", "password_changed_at")
    if _has_column("employees", "must_change_password"):
        op.drop_column("employees", "must_change_password")
