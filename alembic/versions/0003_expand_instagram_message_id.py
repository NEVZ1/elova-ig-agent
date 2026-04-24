"""expand instagram_message_id

Revision ID: 0003_expand_instagram_message_id
Revises: 0002_followup_anchor
Create Date: 2026-04-24

"""

from alembic import op
import sqlalchemy as sa

revision = "0003_expand_instagram_message_id"
down_revision = "0002_followup_anchor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Meta message IDs can exceed 128 chars, so store as TEXT.
    op.alter_column(
        "messages",
        "instagram_message_id",
        existing_type=sa.String(length=128),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "messages",
        "instagram_message_id",
        existing_type=sa.Text(),
        type_=sa.String(length=128),
        existing_nullable=True,
    )

