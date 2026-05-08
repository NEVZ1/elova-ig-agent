"""sales readiness fields

Revision ID: 0004_sales_readiness_fields
Revises: 0003_expand_instagram_message_id
Create Date: 2026-05-08

"""

from alembic import op
import sqlalchemy as sa

revision = "0004_sales_readiness_fields"
down_revision = "0003_expand_instagram_message_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("venue_city", sa.String(length=128), nullable=True))
    op.add_column("leads", sa.Column("project_value_estimate", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("preferred_channel", sa.String(length=32), nullable=True))
    op.add_column("leads", sa.Column("urgency_level", sa.String(length=32), nullable=True))
    op.add_column("leads", sa.Column("owner", sa.String(length=128), nullable=True))
    op.add_column("leads", sa.Column("proposal_status", sa.String(length=32), nullable=False, server_default="none"))
    op.add_column("leads", sa.Column("handoff_required", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("leads", sa.Column("handoff_reason", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("proposal_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "proposal_sent_at")
    op.drop_column("leads", "handoff_reason")
    op.drop_column("leads", "handoff_required")
    op.drop_column("leads", "proposal_status")
    op.drop_column("leads", "owner")
    op.drop_column("leads", "urgency_level")
    op.drop_column("leads", "preferred_channel")
    op.drop_column("leads", "project_value_estimate")
    op.drop_column("leads", "venue_city")
