-- Forward-looking claim expectations for compose framing / desk "what to watch".
-- Consumed by expectation_tracking_service + package_compose_enrichment_service.

CREATE TABLE IF NOT EXISTS intelligence.narrative_expectations (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    domain_key TEXT NOT NULL,
    storyline_id BIGINT,
    source_claim_id BIGINT,
    context_id BIGINT,
    claim_text TEXT NOT NULL,
    subject_text TEXT,
    expected_outcome TEXT,
    due_date DATE,
    due_date_precision TEXT NOT NULL DEFAULT 'day',
    status TEXT NOT NULL DEFAULT 'open',
    resolved_at TIMESTAMPTZ,
    outcome_event_id BIGINT,
    outcome_summary TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT narrative_expectations_status_chk
      CHECK (status IN ('open', 'due_soon', 'overdue', 'resolved', 'expired', 'cancelled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_narrative_expectations_source_claim
  ON intelligence.narrative_expectations (source_claim_id)
  WHERE source_claim_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_narrative_expectations_domain_due
  ON intelligence.narrative_expectations (domain_key, due_date ASC NULLS LAST)
  WHERE status IN ('open', 'due_soon', 'overdue');

CREATE INDEX IF NOT EXISTS idx_narrative_expectations_storyline
  ON intelligence.narrative_expectations (domain_key, storyline_id)
  WHERE storyline_id IS NOT NULL;
