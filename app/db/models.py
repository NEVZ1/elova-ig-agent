from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instagram_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    instagram_username: Mapped[str | None] = mapped_column(String(128), nullable=True)

    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    event_date_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    guest_count: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    budget_min: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    budget_max: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    budget_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="instagram_dm")

    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="greeting")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    followup_state: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    opted_out: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    followup_anchor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    summary: Mapped["ConversationSummary | None"] = relationship(back_populates="lead", uselist=False)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"))

    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # inbound | outbound | system
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="instagram")
    # Meta message IDs can be longer than 128 chars.
    instagram_message_id: Mapped[str | None] = mapped_column(Text(), nullable=True)

    text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_lead_id_created_at", "lead_id", "created_at"),)


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), unique=True)

    summary_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    key_facts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="summary")
