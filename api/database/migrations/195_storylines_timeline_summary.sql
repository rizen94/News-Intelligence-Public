-- Migration 195: timeline_summary on domain storylines (timeline_generation automation, backlog_metrics)
-- Prior code referenced s.timeline_summary; column was never added.

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT d.schema_name FROM public.domains d WHERE d.is_active = true
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = schema_name AND table_name = 'storylines'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS timeline_summary TEXT',
                schema_name
            );
            EXECUTE format(
                'COMMENT ON COLUMN %I.storylines.timeline_summary IS %L',
                schema_name,
                'Short narrative built from chronological_events for timeline_generation; optional.'
            );
        END IF;
    END LOOP;
    RAISE NOTICE 'Migration 195: timeline_summary column ensured for active domain storylines';
END $$;
