from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7a1f3c2b9d10"
down_revision = "5f43318b01b9"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "attendance_correction_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False, index=True),
        sa.Column("request_type", sa.Enum("FORGOT_PUNCH_IN", "FORGOT_PUNCH_OUT", "CORRECTION", name="correction_request_type"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("requested_punch_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_punch_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="correction_status"), nullable=False),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("attendance_correction_requests")
    op.execute("DROP TYPE IF EXISTS correction_request_type")
    op.execute("DROP TYPE IF EXISTS correction_status")
