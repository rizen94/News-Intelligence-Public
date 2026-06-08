-- Migration 227: Canonical politics/finance schemas — drop politics_2 / finance_2 stubs
--
-- Widow state: live row counts live in ``politics`` and ``finance`` (legacy silos).
-- ``public.domains`` still pointed at ``politics_2`` / ``finance_2`` (partial forks).
-- Do NOT apply 219 DROP+RENAME here — that destroys the primary silos.
--
-- Prerequisite: backup. Optional audit:
--   PYTHONPATH=api uv run python api/scripts/audit_politics_finance_schemas.py

BEGIN;

-- Retired URL/domain_key strings (same as migration 219)
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

-- Remove partial fork silos (canonical data remains in politics / finance)
DROP SCHEMA IF EXISTS politics_2 CASCADE;
DROP SCHEMA IF EXISTS finance_2 CASCADE;

DO $$
BEGIN
  RAISE NOTICE 'Migration 227: public.domains → politics/finance; dropped politics_2 and finance_2';
END $$;

COMMIT;
