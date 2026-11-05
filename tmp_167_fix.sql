-- Patch remaining domain schemas one at a time to avoid deadlocks

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN SELECT unnest(ARRAY['artificial_intelligence', 'legal', 'medicine', 'neurodiversity']) AS schema_name LOOP
    EXECUTE format(
      'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS enrichment_attempts SMALLINT DEFAULT 0',
      r.schema_name
    );
    EXECUTE format(
      'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS enrichment_status VARCHAR(20) DEFAULT NULL',
      r.schema_name
    );
    -- Index for backlog queries (pending items with low attempt count)
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS idx_%I_articles_enrichment_backlog ON %I.articles (enrichment_attempts, created_at DESC) WHERE enrichment_status IS NULL OR enrichment_status IN (''pending'', ''failed'')',
      r.schema_name, r.schema_name
    );
    -- Backfill: enriched items (long content), failed items (empty content)
    EXECUTE format(
      'UPDATE %I.articles SET enrichment_status = ''enriched'' WHERE LENGTH(content) >= 500 AND enrichment_status IS NULL',
      r.schema_name
    );
    EXECUTE format(
      'UPDATE %I.articles SET enrichment_status = ''failed'', enrichment_attempts = 1 WHERE (content IS NULL OR content = '''') AND url IS NOT NULL AND url != '''' AND enrichment_status IS NULL',
      r.schema_name
    );
    RAISE NOTICE 'Patched domain: %', r.schema_name;
  END LOOP;
END $$;
