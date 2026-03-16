-- Migration 165: Storyline quality integration and living-by-default support.
-- Adds min_quality_tier, quality_metrics to storylines; adds 'suggest_only' to automation_mode.
-- See docs/STORYLINE_ENHANCEMENT_SPEC.md (or STORYLINE_V6_ASSESSMENT.md).

DO $$
DECLARE
    s TEXT;
    con_name TEXT;
BEGIN
    FOREACH s IN ARRAY ARRAY['politics', 'finance', 'science_tech']
    LOOP
        -- Quality-aware discovery: minimum tier allowed (1=best, 4=worst)
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS min_quality_tier SMALLINT DEFAULT 2 CHECK (min_quality_tier >= 1 AND min_quality_tier <= 4)',
            s
        );
        -- Aggregate quality metrics (avg_tier, fact_density_avg, filter_stats, trends)
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS quality_metrics JSONB DEFAULT %L',
            s, '{}'
        );
        -- Allow 'suggest_only' in automation_mode (suggestions only, no auto-add)
        -- Drop default check name if present (PostgreSQL names it storylines_automation_mode_check)
        EXECUTE format('ALTER TABLE %I.storylines DROP CONSTRAINT IF EXISTS storylines_automation_mode_check', s);
        EXECUTE format('ALTER TABLE %I.storylines DROP CONSTRAINT IF EXISTS chk_storyline_automation_mode', s);
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD CONSTRAINT chk_storyline_automation_mode CHECK (automation_mode IN (''disabled'', ''manual'', ''suggest_only'', ''auto_approve'', ''review_queue''))',
            s
        );
        RAISE NOTICE 'Applied storyline quality integration to %.storylines', s;
    END LOOP;
END $$;

DO $$
DECLARE s TEXT;
BEGIN
    FOREACH s IN ARRAY ARRAY['politics', 'finance', 'science_tech']
    LOOP
        EXECUTE format('COMMENT ON COLUMN %I.storylines.min_quality_tier IS %L', s, 'Minimum article quality_tier allowed (1=best, 4=worst). Used in discovery.');
        EXECUTE format('COMMENT ON COLUMN %I.storylines.quality_metrics IS %L', s, 'Aggregate quality stats: avg_tier, fact_density_avg, filter_counts, last_quality_update');
    END LOOP;
END $$;
