-- Migration 178: timeline_events_generated on domain articles (required by event_extraction UPDATE)
-- Migration 007 only targeted legacy public.articles; automation_manager sets this column per domain.

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT d.schema_name FROM public.domains d WHERE d.is_active = true
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS timeline_events_generated INTEGER DEFAULT 0',
            schema_name
        );
        RAISE NOTICE 'Migration 178: timeline_events_generated on %.articles', schema_name;
    END LOOP;
END $$;
