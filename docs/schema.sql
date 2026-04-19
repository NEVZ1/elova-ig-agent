-- Generated from Alembic migration `alembic/versions/0001_init.py`

CREATE TABLE leads (
  id uuid PRIMARY KEY,
  instagram_user_id varchar(64) NOT NULL UNIQUE,
  instagram_username varchar(128),
  name varchar(256),
  event_type varchar(128),
  event_date date,
  event_date_text varchar(128),
  guest_count integer,
  budget_min integer,
  budget_max integer,
  budget_currency varchar(8),
  source varchar(64) NOT NULL DEFAULT 'instagram_dm',
  stage varchar(32) NOT NULL DEFAULT 'greeting',
  status varchar(32) NOT NULL DEFAULT 'new',
  followup_state varchar(32) NOT NULL DEFAULT 'none',
  opted_out boolean NOT NULL DEFAULT false,
  last_message_at timestamptz,
  last_inbound_at timestamptz,
  last_outbound_at timestamptz,
  followup_anchor_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_leads_status ON leads(status);
CREATE INDEX ix_leads_stage ON leads(stage);
CREATE INDEX ix_leads_last_inbound_at ON leads(last_inbound_at);
CREATE INDEX ix_leads_followup_anchor_at ON leads(followup_anchor_at);

CREATE TABLE messages (
  id uuid PRIMARY KEY,
  lead_id uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  direction varchar(16) NOT NULL,
  channel varchar(16) NOT NULL DEFAULT 'instagram',
  instagram_message_id varchar(128),
  text text,
  raw_payload jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_messages_lead_id_created_at ON messages(lead_id, created_at);

CREATE TABLE conversation_summaries (
  id uuid PRIMARY KEY,
  lead_id uuid NOT NULL UNIQUE REFERENCES leads(id) ON DELETE CASCADE,
  summary_text text,
  key_facts jsonb,
  last_message_id uuid,
  updated_at timestamptz NOT NULL DEFAULT now()
);
