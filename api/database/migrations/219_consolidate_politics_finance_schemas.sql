-- Migration 219: Canonical Postgres schemas ``politics`` and ``finance`` (drop legacy stubs, rename ``*_2``).
--
-- Prerequisites:
--   1. Full DB backup.
--   2. PYTHONPATH=api uv run python api/scripts/audit_politics_finance_schemas.py
--   3. If legacy ``politics`` / ``finance`` have rows, copy into ``politics_2`` / ``finance_2`` first
--      (api/scripts/copy_domain_silo_table_data.py), then re-run audit.
--
-- Idempotent: skips rename when target schema already exists.

BEGIN;

-- Defensive cleanup of retired template domain_key strings (211 should have applied).
UPDATE intelligence.contexts SET domain_key = 'politics' WHERE domain_key IN ('politics-2', 'politics2');
UPDATE intelligence.contexts SET domain_key = 'finance' WHERE domain_key IN ('finance-2', 'finance2');

DELETE FROM intelligence.article_to_context WHERE domain_key IN ('politics-2', 'politics2', 'finance-2', 'finance2');
DELETE FROM intelligence.entity_profiles WHERE domain_key IN ('politics-2', 'politics2', 'finance-2', 'finance2');
DELETE FROM intelligence.article_duplicate_sources WHERE domain_key IN ('politics-2', 'politics2', 'finance-2', 'finance2');
DELETE FROM intelligence.claim_subject_gap_catalog WHERE domain_key IN ('politics-2', 'politics2', 'finance-2', 'finance2');
DELETE FROM intelligence.content_refinement_queue WHERE domain_key IN ('politics-2', 'politics2', 'finance-2', 'finance2');
UPDATE intelligence.narrative_threads SET domain_key = 'politics' WHERE domain_key IN ('politics-2', 'politics2');
UPDATE intelligence.narrative_threads SET domain_key = 'finance' WHERE domain_key IN ('finance-2', 'finance2');

UPDATE intelligence.tracked_events
SET domain_keys = array_replace(
    array_replace(
      array_replace(
        array_replace(COALESCE(domain_keys, '{}'::text[]), 'politics-2', 'politics'),
        'finance-2', 'finance'
      ),
      'politics2', 'politics'
    ),
    'finance2', 'finance'
  )
WHERE domain_keys && ARRAY['politics-2', 'finance-2', 'politics2', 'finance2']::text[];

-- Queue / catalog columns that store schema names (migration 210 used *_2).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'ml_processing_queue'
  ) THEN
    UPDATE public.ml_processing_queue SET schema_name = 'politics' WHERE schema_name = 'politics_2';
    UPDATE public.ml_processing_queue SET schema_name = 'finance' WHERE schema_name = 'finance_2';
  END IF;
END $$;

UPDATE public.domains
SET schema_name = 'politics',
    description = regexp_replace(COALESCE(description, ''), 'politics_2', 'politics', 'gi')
WHERE domain_key = 'politics';

UPDATE public.domains
SET schema_name = 'finance',
    description = regexp_replace(COALESCE(description, ''), 'finance_2', 'finance', 'gi')
WHERE domain_key = 'finance';

-- Drop retired legacy silos so names are free for RENAME (data must already live in *_2).
DROP SCHEMA IF EXISTS politics CASCADE;
DROP SCHEMA IF EXISTS finance CASCADE;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'politics_2')
     AND NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'politics') THEN
    ALTER SCHEMA politics_2 RENAME TO politics;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'finance_2')
     AND NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'finance') THEN
    ALTER SCHEMA finance_2 RENAME TO finance;
  END IF;
END $$;

DO $$
BEGIN
  RAISE NOTICE 'Migration 219: politics/finance schemas unified (politics_2→politics, finance_2→finance)';
END $$;

COMMIT;
