-- Enrichment tracking: attempt count and status for content enrichment backlog management.
-- Used by content_enrichment (batch + inline at RSS) to avoid retrying forever and to reorder queue.
DO $$
DECLARE
  r RECORD;
  s TEXT;
BEGIN
  FOR r IN SELECT unnest(ARRAY['politics', 'finance', 'science_tech']) AS schema_name LOOP
    s := r.schema_name;
    EXECUTE format('ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS enrichment_attempts SMALLINT DEFAULT 0', s);
    EXECUTE format('ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS enrichment_status VARCHAR(20) DEFAULT NULL', s);
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS idx_%I_articles_enrichment_backlog ON %I.articles (enrichment_attempts, created_at DESC) WHERE enrichment_status IS NULL OR enrichment_status IN (''pending'', ''failed'')',
      s, s
    );
    -- Backfill: already-enriched (long content), already-failed (empty content)
    EXECUTE format('UPDATE %I.articles SET enrichment_status = ''enriched'' WHERE LENGTH(content) >= 500 AND enrichment_status IS NULL', s);
    EXECUTE format('UPDATE %I.articles SET enrichment_status = ''failed'', enrichment_attempts = 1 WHERE (content IS NULL OR content = '''') AND url IS NOT NULL AND url != '''' AND enrichment_status IS NULL', s);
  END LOOP;
END $$;
