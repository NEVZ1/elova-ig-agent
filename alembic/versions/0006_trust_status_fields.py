"""trust status fields

Revision ID: 0006_trust_status_fields
Revises: 0005_crm_maturity_fields
Create Date: 2026-05-08

"""

from alembic import op
import sqlalchemy as sa

revision = "0006_trust_status_fields"
down_revision = "0005_crm_maturity_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("review_status", sa.String(length=32), nullable=False, server_default="not_requested"))
    op.add_column("leads", sa.Column("testimonial_status", sa.String(length=32), nullable=False, server_default="not_requested"))
    op.add_column("leads", sa.Column("referral_status", sa.String(length=32), nullable=False, server_default="not_requested"))


def downgrade() -> None:
    op.drop_column("leads", "referral_status")
    op.drop_column("leads", "testimonial_status")
    op.drop_column("leads", "review_status")
