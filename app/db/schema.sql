CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS competitors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  website_url TEXT,
  category TEXT NOT NULL DEFAULT 'student_help_service',
  geo TEXT,
  pricing_model TEXT,
  offer_summary TEXT,
  discovered_from TEXT NOT NULL DEFAULT 'seed',
  confidence NUMERIC(3,2) NOT NULL DEFAULT 0.50,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS platforms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  platform_type TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  handle TEXT,
  description TEXT,
  language TEXT,
  geo TEXT,
  audience_size INTEGER,
  activity_last_seen_at TIMESTAMPTZ,
  rules_text TEXT,
  commercial_tolerance SMALLINT NOT NULL DEFAULT 0,
  risk_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  discovery_source TEXT NOT NULL DEFAULT 'manual',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  platform_id UUID NOT NULL REFERENCES platforms(id),
  mention_id UUID,
  priority SMALLINT NOT NULL DEFAULT 3,
  opportunity_score NUMERIC(5,2) NOT NULL DEFAULT 0,
  risk_score NUMERIC(5,2) NOT NULL DEFAULT 0,
  recommended_action TEXT,
  message_draft TEXT,
  utm_campaign TEXT,
  operator_id UUID,
  reviewer_verdict TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mentions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  platform_id UUID NOT NULL REFERENCES platforms(id),
  competitor_id UUID REFERENCES competitors(id),
  mention_type TEXT NOT NULL,
  source_url TEXT NOT NULL,
  author_handle TEXT,
  published_at TIMESTAMPTZ,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  text TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  fingerprint TEXT NOT NULL,
  detected_intents JSONB NOT NULL DEFAULT '[]'::jsonb,
  trigger_hits JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_task_id UUID REFERENCES tasks(id),
  CONSTRAINT uq_mention_source_fingerprint UNIQUE (source_url, fingerprint)
);

CREATE TABLE IF NOT EXISTS triggers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL,
  regex_patterns JSONB,
  keywords JSONB,
  negative_keywords JSONB,
  weight NUMERIC(4,2) NOT NULL DEFAULT 1.00,
  enabled BOOLEAN NOT NULL DEFAULT true,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin_contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  platform_id UUID NOT NULL REFERENCES platforms(id),
  contact_type TEXT NOT NULL,
  contact_value TEXT NOT NULL,
  source TEXT NOT NULL,
  confidence NUMERIC(3,2) NOT NULL DEFAULT 0.5,
  last_verified_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS logs (
  id BIGSERIAL PRIMARY KEY,
  run_id UUID,
  component TEXT NOT NULL,
  level TEXT NOT NULL,
  event TEXT NOT NULL,
  url TEXT,
  http_status INTEGER,
  error_code TEXT,
  message TEXT NOT NULL,
  payload JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_mentions_fingerprint ON mentions(fingerprint);
CREATE INDEX IF NOT EXISTS ix_logs_component_status ON logs(component, http_status, created_at DESC);
