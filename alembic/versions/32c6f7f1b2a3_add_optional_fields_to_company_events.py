from alembic import op
import sqlalchemy as sa

revision = "32c6f7f1b2a3"
down_revision = "5f43318b01b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_events", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("company_events", sa.Column("image_url", sa.String(length=500), nullable=True))
    op.add_column("company_events", sa.Column("location", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("company_events", "location")
    op.drop_column("company_events", "image_url")
    op.drop_column("company_events", "description")
