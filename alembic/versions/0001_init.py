"""init

Revision ID: 0001_init
Revises: 
Create Date: 2026-04-19

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("instagram_user_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("instagram_username", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("event_date_text", sa.String(length=128), nullable=True),
        sa.Column("guest_count", sa.Integer(), nullable=True),
        sa.Column("budget_min", sa.Integer(), nullable=True),
        sa.Column("budget_max", sa.Integer(), nullable=True),
        sa.Column("budget_currency", sa.String(length=8), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="instagram_dm"),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="greeting"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("followup_state", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("opted_out", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_stage", "leads", ["stage"])
    op.create_index("ix_leads_last_inbound_at", "leads", ["last_inbound_at"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False, server_default="instagram"),
        sa.Column("instagram_message_id", sa.String(length=128), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_lead_id_created_at", "messages", ["lead_id", "created_at"])

    op.create_table(
        "conversation_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("key_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("conversation_summaries")
    op.drop_index("ix_messages_lead_id_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_leads_last_inbound_at", table_name="leads")
    op.drop_index("ix_leads_stage", table_name="leads")
    op.drop_index("ix_leads_status", table_name="leads")
    op.drop_table("leads")

