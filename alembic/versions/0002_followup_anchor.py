"""followup anchor

Revision ID: 0002_followup_anchor
Revises: 0001_init
Create Date: 2026-04-19

"""

from alembic import op
import sqlalchemy as sa

revision = "0002_followup_anchor"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("followup_anchor_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_leads_followup_anchor_at", "leads", ["followup_anchor_at"])


def downgrade() -> None:
    op.drop_index("ix_leads_followup_anchor_at", table_name="leads")
    op.drop_column("leads", "followup_anchor_at")

