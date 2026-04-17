-- Migration 211: Canonical domain keys ``politics`` and ``finance`` for template silos
-- (schemas stay ``politics_2`` and ``finance_2``).
--
-- Prerequisites:
--   1. Migration **210** applied (legacy ``politics`` / ``finance`` / ``science-tech`` rows inactive).
--   2. Data copied into ``politics_2`` / ``finance_2`` as needed; feeds cut over.
--
-- This migration:
--   - Deletes inactive stub rows that still hold domain_key ``politics`` / ``finance`` (from legacy era).
--   - Renames ``politics-2`` → ``politics`` and ``finance-2`` → ``finance`` in ``public.domains``.
--   - Repoints ``domain_key`` strings and ``tracked_events.domain_keys`` tokens app-wide.

BEGIN;

-- Remove inactive legacy registry rows so ``politics`` / ``finance`` keys are free
DELETE FROM public.domain_metadata
WHERE domain_id IN (
  SELECT id FROM public.domains
  WHERE domain_key IN ('politics', 'finance') AND is_active = false
);
DELETE FROM public.domains
WHERE domain_key IN ('politics', 'finance') AND is_active = false;

UPDATE public.domains
SET domain_key = 'politics',
    name = 'Politics',
    description = COALESCE(NULLIF(description, ''), 'Politics silo (schema politics_2).')
WHERE domain_key = 'politics-2';

UPDATE public.domains
SET domain_key = 'finance',
    name = 'Finance',
    description = COALESCE(NULLIF(description, ''), 'Finance silo (schema finance_2).')
WHERE domain_key = 'finance-2';

-- Intelligence: template keys → canonical
UPDATE intelligence.contexts SET domain_key = 'politics' WHERE domain_key = 'politics-2';
UPDATE intelligence.contexts SET domain_key = 'finance' WHERE domain_key = 'finance-2';

UPDATE intelligence.article_to_context a SET domain_key = 'politics'
WHERE domain_key = 'politics-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_to_context x
    WHERE x.domain_key = 'politics' AND x.article_id = a.article_id
  );
DELETE FROM intelligence.article_to_context WHERE domain_key = 'politics-2';

UPDATE intelligence.article_to_context a SET domain_key = 'finance'
WHERE domain_key = 'finance-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_to_context x
    WHERE x.domain_key = 'finance' AND x.article_id = a.article_id
  );
DELETE FROM intelligence.article_to_context WHERE domain_key = 'finance-2';

UPDATE intelligence.entity_profiles SET domain_key = 'politics'
WHERE domain_key = 'politics-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.entity_profiles e2
    WHERE e2.domain_key = 'politics' AND e2.canonical_entity_id = intelligence.entity_profiles.canonical_entity_id
  );
DELETE FROM intelligence.entity_profiles WHERE domain_key = 'politics-2';

UPDATE intelligence.entity_profiles SET domain_key = 'finance'
WHERE domain_key = 'finance-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.entity_profiles e2
    WHERE e2.domain_key = 'finance' AND e2.canonical_entity_id = intelligence.entity_profiles.canonical_entity_id
  );
DELETE FROM intelligence.entity_profiles WHERE domain_key = 'finance-2';

UPDATE intelligence.article_duplicate_sources a SET domain_key = 'politics'
WHERE domain_key = 'politics-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_duplicate_sources x
    WHERE x.domain_key = 'politics'
      AND x.canonical_article_id = a.canonical_article_id
      AND x.duplicate_url IS NOT DISTINCT FROM a.duplicate_url
      AND x.duplicate_source_domain IS NOT DISTINCT FROM a.duplicate_source_domain
      AND x.duplicate_title IS NOT DISTINCT FROM a.duplicate_title
  );
DELETE FROM intelligence.article_duplicate_sources WHERE domain_key = 'politics-2';

UPDATE intelligence.article_duplicate_sources a SET domain_key = 'finance'
WHERE domain_key = 'finance-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_duplicate_sources x
    WHERE x.domain_key = 'finance'
      AND x.canonical_article_id = a.canonical_article_id
      AND x.duplicate_url IS NOT DISTINCT FROM a.duplicate_url
      AND x.duplicate_source_domain IS NOT DISTINCT FROM a.duplicate_source_domain
      AND x.duplicate_title IS NOT DISTINCT FROM a.duplicate_title
  );
DELETE FROM intelligence.article_duplicate_sources WHERE domain_key = 'finance-2';

UPDATE intelligence.claim_subject_gap_catalog a SET domain_key = 'politics'
WHERE domain_key = 'politics-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.claim_subject_gap_catalog x
    WHERE x.domain_key = 'politics' AND x.subject_norm = a.subject_norm
  );
DELETE FROM intelligence.claim_subject_gap_catalog WHERE domain_key = 'politics-2';

UPDATE intelligence.claim_subject_gap_catalog a SET domain_key = 'finance'
WHERE domain_key = 'finance-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.claim_subject_gap_catalog x
    WHERE x.domain_key = 'finance' AND x.subject_norm = a.subject_norm
  );
DELETE FROM intelligence.claim_subject_gap_catalog WHERE domain_key = 'finance-2';

UPDATE intelligence.content_refinement_queue a SET domain_key = 'politics'
WHERE domain_key = 'politics-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.content_refinement_queue x
    WHERE x.domain_key = 'politics'
      AND x.storyline_id = a.storyline_id
      AND x.job_type IS NOT DISTINCT FROM a.job_type
  );
DELETE FROM intelligence.content_refinement_queue WHERE domain_key = 'politics-2';

UPDATE intelligence.content_refinement_queue a SET domain_key = 'finance'
WHERE domain_key = 'finance-2'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.content_refinement_queue x
    WHERE x.domain_key = 'finance'
      AND x.storyline_id = a.storyline_id
      AND x.job_type IS NOT DISTINCT FROM a.job_type
  );
DELETE FROM intelligence.content_refinement_queue WHERE domain_key = 'finance-2';

UPDATE intelligence.narrative_threads SET domain_key = 'politics' WHERE domain_key = 'politics-2';
UPDATE intelligence.narrative_threads SET domain_key = 'finance' WHERE domain_key = 'finance-2';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'intelligence' AND table_name = 'legislative_article_scans'
  ) THEN
    UPDATE intelligence.legislative_article_scans SET domain_key = 'politics' WHERE domain_key = 'politics-2';
    UPDATE intelligence.legislative_article_scans SET domain_key = 'finance' WHERE domain_key = 'finance-2';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'intelligence' AND table_name = 'legislative_references'
  ) THEN
    UPDATE intelligence.legislative_references lr SET domain_key = 'politics'
    WHERE domain_key = 'politics-2'
      AND NOT EXISTS (
        SELECT 1 FROM intelligence.legislative_references x
        WHERE x.domain_key = 'politics' AND x.article_id = lr.article_id
      );
    DELETE FROM intelligence.legislative_references WHERE domain_key = 'politics-2';

    UPDATE intelligence.legislative_references lr SET domain_key = 'finance'
    WHERE domain_key = 'finance-2'
      AND NOT EXISTS (
        SELECT 1 FROM intelligence.legislative_references x
        WHERE x.domain_key = 'finance' AND x.article_id = lr.article_id
      );
    DELETE FROM intelligence.legislative_references WHERE domain_key = 'finance-2';
  END IF;
END $$;

UPDATE intelligence.tracked_events
SET domain_keys =
  array_replace(
    array_replace(
      COALESCE(domain_keys, '{}'::text[]),
      'politics-2'::text,
      'politics'::text
    ),
    'finance-2'::text,
    'finance'::text
  )
WHERE domain_keys && ARRAY['politics-2', 'finance-2']::text[];

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'intelligence' AND table_name = 'storyline_rag_context'
  ) THEN
    UPDATE intelligence.storyline_rag_context SET domain_key = 'politics' WHERE domain_key = 'politics-2';
    UPDATE intelligence.storyline_rag_context SET domain_key = 'finance' WHERE domain_key = 'finance-2';
  END IF;
END $$;

COMMIT;
