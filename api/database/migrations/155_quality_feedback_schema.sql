-- Migration 155: Quality feedback and source reliability (pipeline enhancements P0)
-- See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md
-- Tables: claim_validations, event_validations, source_reliability

-- Claim validations: feedback on extracted claims for quality loop
CREATE TABLE IF NOT EXISTS intelligence.claim_validations (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('accurate', 'corrected', 'rejected')),
    accuracy_score FLOAT CHECK (accuracy_score IS NULL OR (accuracy_score >= 0 AND accuracy_score <= 1)),
    corrected_text TEXT,
    validated_at TIMESTAMPTZ DEFAULT NOW(),
    validated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_claim_validations_claim_id ON intelligence.claim_validations(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_validations_validated_at ON intelligence.claim_validations(validated_at DESC);
COMMENT ON TABLE intelligence.claim_validations IS 'Feedback on extracted claims; feeds extraction_metrics and source quality';

-- Event validations: feedback on tracked events
CREATE TABLE IF NOT EXISTS intelligence.event_validations (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('accurate', 'corrected', 'rejected')),
    corrections JSONB DEFAULT '{}',
    validated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_validations_event_id ON intelligence.event_validations(event_id);
CREATE INDEX IF NOT EXISTS idx_event_validations_validated_at ON intelligence.event_validations(validated_at DESC);
COMMENT ON TABLE intelligence.event_validations IS 'Feedback on tracked events; improves event detection tuning';

-- Source reliability: per-source quality for collection prioritization
CREATE TABLE IF NOT EXISTS intelligence.source_reliability (
    source_name TEXT PRIMARY KEY,
    accuracy_score FLOAT CHECK (accuracy_score IS NULL OR (accuracy_score >= 0 AND accuracy_score <= 1)),
    exclusive_stories_count INTEGER DEFAULT 0,
    correction_rate FLOAT CHECK (correction_rate IS NULL OR (correction_rate >= 0 AND correction_rate <= 1)),
    last_collection_at TIMESTAMPTZ,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE intelligence.source_reliability IS 'Per-source quality; used by Collection Governor for prioritization';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.claim_validations TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.event_validations TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.source_reliability TO newsapp;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intelligence TO newsapp;
