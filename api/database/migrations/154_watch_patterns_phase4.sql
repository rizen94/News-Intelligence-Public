-- Migration 154: Phase 4 RAG — watch patterns and pattern match results
-- See docs/RAG_ENHANCEMENT_ROADMAP.md. Enables pattern matching against content and alert generation.

CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;

-- Watch patterns: what to watch for by story type (court_case, election, person_tenure, economic_event)
CREATE TABLE IF NOT EXISTS intelligence.watch_patterns (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    storyline_id INTEGER,
    story_type VARCHAR(50) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL CHECK (pattern_type IN (
        'keyword', 'entity_action', 'document', 'timeline'
    )),
    pattern_config JSONB NOT NULL DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_watch_patterns_domain_story ON intelligence.watch_patterns(domain_key, storyline_id);
CREATE INDEX IF NOT EXISTS idx_watch_patterns_story_type ON intelligence.watch_patterns(story_type);

COMMENT ON TABLE intelligence.watch_patterns IS 'Phase 4: patterns to match against new content; story_type drives default keyword/entity sets';

-- Pattern matches: record when content matches a pattern (for significance and alerting)
CREATE TABLE IF NOT EXISTS intelligence.pattern_matches (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    storyline_id INTEGER,
    watch_pattern_id INTEGER REFERENCES intelligence.watch_patterns(id) ON DELETE SET NULL,
    content_ref_type VARCHAR(50) DEFAULT 'context',
    content_ref_id INTEGER,
    matched_text TEXT,
    significance_score DECIMAL(3,2) CHECK (significance_score >= 0 AND significance_score <= 1),
    alert_created BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pattern_matches_domain_story ON intelligence.pattern_matches(domain_key, storyline_id);
CREATE INDEX IF NOT EXISTS idx_pattern_matches_created ON intelligence.pattern_matches(created_at DESC);

COMMENT ON TABLE intelligence.pattern_matches IS 'Phase 4: record of pattern matches; alert_created when watchlist_alert was generated';

-- Allow watchlist_alerts to use alert_type 'pattern_match'
DO $$
DECLARE
    conname TEXT;
BEGIN
    SELECT conname INTO conname
    FROM pg_constraint
    WHERE conrelid = 'public.watchlist_alerts'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%alert_type%';
    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.watchlist_alerts DROP CONSTRAINT %I', conname);
        ALTER TABLE public.watchlist_alerts ADD CONSTRAINT watchlist_alerts_alert_type_check
            CHECK (alert_type IN (
                'reactivation', 'new_event', 'source_corroboration',
                'escalation', 'resolution', 'weekly_digest', 'pattern_match'
            ));
    END IF;
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

GRANT SELECT, INSERT, UPDATE ON intelligence.watch_patterns TO newsapp;
GRANT SELECT, INSERT, UPDATE ON intelligence.pattern_matches TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.watch_patterns_id_seq TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.pattern_matches_id_seq TO newsapp;
