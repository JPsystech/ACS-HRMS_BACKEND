from alembic import op
import sqlalchemy as sa

revision = "028_add_birthday_wishes"
down_revision = "027_culture_enhancements"
branch_labels = None
depends_on = None

def _has_table(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()

def upgrade():
    if not _has_table("birthday_wishes"):
        op.create_table(
            "birthday_wishes",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False, index=True),
            sa.Column("date", sa.Date(), nullable=False, index=True),
            sa.Column("sender_id", sa.Integer(), nullable=False, index=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
            sa.ForeignKeyConstraint(["sender_id"], ["employees.id"]),
        )

def downgrade():
    if _has_table("birthday_wishes"):
        op.drop_table("birthday_wishes")
