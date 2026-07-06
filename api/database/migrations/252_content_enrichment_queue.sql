-- Migration 252: Per-domain content_enrichment_queue (v10.1 spine queues)

BEGIN;

DO $$
DECLARE
  r RECORD;
  stmt TEXT;
BEGIN
  FOR r IN
    SELECT schema_name
    FROM public.domains
    WHERE is_active = true
      AND schema_name IS NOT NULL
      AND schema_name <> ''
  LOOP
    stmt := format(
      $sql$
      CREATE TABLE IF NOT EXISTS %I.content_enrichment_queue (
          id BIGSERIAL PRIMARY KEY,
          article_id INTEGER NOT NULL REFERENCES %I.articles(id) ON DELETE CASCADE,
          status VARCHAR(20) NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
          priority INTEGER NOT NULL DEFAULT 2,
          retry_count INTEGER NOT NULL DEFAULT 0,
          max_retries INTEGER NOT NULL DEFAULT 5,
          last_attempt_at TIMESTAMPTZ,
          next_retry_at TIMESTAMPTZ,
          error_message TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          started_at TIMESTAMPTZ,
          completed_at TIMESTAMPTZ,
          metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
          UNIQUE (article_id)
      );
      CREATE INDEX IF NOT EXISTS idx_%s_enrich_q_pending
          ON %I.content_enrichment_queue (priority DESC, created_at ASC)
          WHERE status = 'pending';
      $sql$,
      r.schema_name,
      r.schema_name,
      replace(r.schema_name, '-', '_'),
      r.schema_name
    );
    BEGIN
      EXECUTE stmt;
    EXCEPTION
      WHEN undefined_table THEN
        RAISE NOTICE '252 skip enrichment queue schema % (missing articles)', r.schema_name;
    END;
  END LOOP;
END $$;

COMMIT;
