-- Create expression indexes for pass-marker JSONB predicates in each domain schema
DO $$
DECLARE
    schemas text[] := ARRAY['legal', 'medicine', 'artificial_intelligence', 'politics', 'finance'];
    schema text;
    phases text[] := ARRAY['unified_intake_extraction', 'claim_extraction', 'event_extraction'];
    phase text;
BEGIN
    FOREACH schema IN ARRAY schemas
    LOOP
        FOREACH phase IN ARRAY phases
        LOOP
            EXECUTE format($f$
                CREATE INDEX IF NOT EXISTS idx_%I_metadata_pipeline_%I_last_terminal_state
                ON %I.articles ((metadata->'pipeline'->%L->>'last_terminal_state'))
                WHERE metadata->'pipeline'->%L->>'last_terminal_state' IS NOT NULL
                  AND enrichment_status = 'enriched'
            $f$, schema, phase, schema, phase, phase);
        END LOOP;

        -- Composite index on articles (enrichment_status, created_at)
        EXECUTE format($f$
            CREATE INDEX IF NOT EXISTS idx_%I_articles_enrichment_status_created_at
            ON %I.articles (enrichment_status, created_at)
        $f$, schema, schema);
    END LOOP;
END $$;

-- Index on versioned_facts (source_claim_id) for anti-join
DO $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_versioned_facts_source_claim_id
    ON intelligence.versioned_facts (source_claim_id);
END $$;

-- Index on automation_run_history for per-replan health queries
DO $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_automation_run_history_phase_name_started_at
    ON intelligence.automation_run_history (phase_name, started_at DESC);
END $$;

-- Note: Retention policy for automation_run_history (e.g., keep 30 days) should be implemented
-- via a periodic cron job or automated task, not enforced via schema constraints.