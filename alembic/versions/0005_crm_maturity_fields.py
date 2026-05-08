"""crm maturity fields

Revision ID: 0005_crm_maturity_fields
Revises: 0004_sales_readiness_fields
Create Date: 2026-05-08

"""

from alembic import op
import sqlalchemy as sa

revision = "0005_crm_maturity_fields"
down_revision = "0004_sales_readiness_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("lost_reason", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("internal_notes", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("next_followup_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "next_followup_at")
    op.drop_column("leads", "internal_notes")
    op.drop_column("leads", "lost_reason")
