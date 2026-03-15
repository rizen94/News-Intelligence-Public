-- Migration 156: Cross-domain correlations (pipeline enhancements P1)
-- See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md
-- Table: intelligence.cross_domain_correlations
-- Also ensure tracked_events has domain_keys for cross-domain synthesis.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'intelligence' AND table_name = 'tracked_events' AND column_name = 'domain_keys'
    ) THEN
        ALTER TABLE intelligence.tracked_events ADD COLUMN domain_keys TEXT[] DEFAULT '{}';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS intelligence.cross_domain_correlations (
    correlation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_1 TEXT NOT NULL,
    domain_2 TEXT NOT NULL,
    entity_profile_ids INT[] DEFAULT '{}',
    event_ids INT[] DEFAULT '{}',
    correlation_strength FLOAT CHECK (correlation_strength IS NULL OR (correlation_strength >= 0 AND correlation_strength <= 1)),
    correlation_type TEXT NOT NULL CHECK (correlation_type IN ('entity_overlap', 'temporal', 'thematic')),
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_cross_domain_correlations_domains ON intelligence.cross_domain_correlations(domain_1, domain_2);
CREATE INDEX IF NOT EXISTS idx_cross_domain_correlations_discovered ON intelligence.cross_domain_correlations(discovered_at DESC);
COMMENT ON TABLE intelligence.cross_domain_correlations IS 'Cross-domain relationships for synthesis and unified timeline';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.cross_domain_correlations TO newsapp;
