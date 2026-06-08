-- Migration 233: Partial indexes for content_enrichment backlog COUNT queries
-- Aligns with backlog_metrics._count_content_enrichment_backlog and enrich_articles_batch selection.

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT d.schema_name FROM public.domains d WHERE d.is_active = true
    LOOP
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%I_articles_enrichment_backlog ON %I.articles (enrichment_attempts ASC NULLS FIRST, created_at DESC) WHERE (enrichment_status IS NULL OR enrichment_status IN (''pending'', ''failed'')) AND url IS NOT NULL AND url <> ''''',
            schema_name,
            schema_name
        );
    END LOOP;
    RAISE NOTICE 'Migration 233: enrichment backlog partial indexes ensured for active domain schemas';
END $$;
