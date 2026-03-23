-- Migration 194: Partial index on domain articles for event-extraction backlog
-- (timeline_processed = false) ordered by published_at — complements migration 177 btree on (timeline_processed).

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT d.schema_name FROM public.domains d WHERE d.is_active = true
    LOOP
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%I_articles_timeline_pending ON %I.articles (published_at DESC NULLS LAST) WHERE timeline_processed = false',
            schema_name,
            schema_name
        );
    END LOOP;
    RAISE NOTICE 'Migration 194: partial timeline backlog indexes ensured for active domain schemas';
END $$;
