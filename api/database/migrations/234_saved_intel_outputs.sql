-- Append-only reading history for generated intel outputs (reports, synthesis, dossiers).
-- Apply: PYTHONPATH=api uv run python api/scripts/run_migration.py 234

CREATE TABLE IF NOT EXISTS intelligence.saved_intel_outputs (
    id SERIAL PRIMARY KEY,
    content_type VARCHAR(64) NOT NULL,
    domain_key VARCHAR(64),
    subject_type VARCHAR(64),
    subject_id INTEGER NOT NULL,
    title TEXT,
    content_md TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_intel_domain
    ON intelligence.saved_intel_outputs(domain_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_saved_intel_subject
    ON intelligence.saved_intel_outputs(subject_type, subject_id);
