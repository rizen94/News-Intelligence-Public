-- Migration 251: Narrow pipeline_status table (interim eligibility before full queues)

BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.pipeline_status (
    schema_name VARCHAR(80) NOT NULL,
    article_id BIGINT NOT NULL,
    phase_name VARCHAR(80) NOT NULL,
    outcome VARCHAR(80),
    terminal_state VARCHAR(80),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (schema_name, article_id, phase_name)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_status_phase_pending
    ON intelligence.pipeline_status (phase_name, schema_name, updated_at)
    WHERE terminal_state IS NULL OR terminal_state = 'failed_needs_retry';

COMMENT ON TABLE intelligence.pipeline_status IS
    'v10.1 narrow pass-marker store; reduces JSONB churn on domain articles.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.pipeline_status TO newsapp;

COMMIT;
