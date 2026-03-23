-- Migration 190: Store silo schema on ml_processing_queue so workers do not resolve article_id
-- by scanning domains (IDs are not unique across per-domain articles tables).
-- Idempotent.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'ml_processing_queue'
  ) THEN
    ALTER TABLE public.ml_processing_queue
      ADD COLUMN IF NOT EXISTS schema_name VARCHAR(128);
    COMMENT ON COLUMN public.ml_processing_queue.schema_name IS
      'Postgres silo schema (e.g. politics, science_tech). Set for all new rows; legacy rows may be NULL (resolved at runtime by scanning active schemas).';
  END IF;
END $$;
