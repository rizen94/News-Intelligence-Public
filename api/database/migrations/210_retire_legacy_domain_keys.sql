-- Migration 210: Repoint intelligence / public references from legacy domain keys
-- (politics, finance, science-tech) to template silos and split default for science-tech.
--
-- Run **after** copying silo data you need from politics → politics_2, finance → finance_2
-- (see api/scripts/copy_domain_silo_table_data.py). This migration does **not** move rows between
-- Postgres schemas — only updates ``domain_key`` / array tokens in shared tables.
--
-- science-tech → artificial-intelligence (navigation default); reclassify ``science_tech`` articles
-- into other silos with a separate script if needed.
--
-- Deactivates legacy rows in ``public.domains`` so the API registry (DB-backed) no longer lists them.

BEGIN;

UPDATE intelligence.contexts SET domain_key = 'politics-2' WHERE domain_key = 'politics';
UPDATE intelligence.contexts SET domain_key = 'finance-2' WHERE domain_key = 'finance';
UPDATE intelligence.contexts SET domain_key = 'artificial-intelligence' WHERE domain_key = 'science-tech';

-- UNIQUE (domain_key, article_id): skip updates that would duplicate an existing target row
UPDATE intelligence.article_to_context a SET domain_key = 'politics-2'
WHERE domain_key = 'politics'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_to_context x
    WHERE x.domain_key = 'politics-2' AND x.article_id = a.article_id
  );
DELETE FROM intelligence.article_to_context WHERE domain_key = 'politics';

UPDATE intelligence.article_to_context a SET domain_key = 'finance-2'
WHERE domain_key = 'finance'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_to_context x
    WHERE x.domain_key = 'finance-2' AND x.article_id = a.article_id
  );
DELETE FROM intelligence.article_to_context WHERE domain_key = 'finance';

UPDATE intelligence.article_to_context a SET domain_key = 'artificial-intelligence'
WHERE domain_key = 'science-tech'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_to_context x
    WHERE x.domain_key = 'artificial-intelligence' AND x.article_id = a.article_id
  );
DELETE FROM intelligence.article_to_context WHERE domain_key = 'science-tech';

UPDATE intelligence.entity_profiles SET domain_key = 'politics-2'
WHERE domain_key = 'politics'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.entity_profiles e2
    WHERE e2.domain_key = 'politics-2' AND e2.canonical_entity_id = intelligence.entity_profiles.canonical_entity_id
  );
DELETE FROM intelligence.entity_profiles WHERE domain_key = 'politics';

UPDATE intelligence.entity_profiles SET domain_key = 'finance-2'
WHERE domain_key = 'finance'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.entity_profiles e2
    WHERE e2.domain_key = 'finance-2' AND e2.canonical_entity_id = intelligence.entity_profiles.canonical_entity_id
  );
DELETE FROM intelligence.entity_profiles WHERE domain_key = 'finance';

UPDATE intelligence.entity_profiles SET domain_key = 'artificial-intelligence'
WHERE domain_key = 'science-tech'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.entity_profiles e2
    WHERE e2.domain_key = 'artificial-intelligence' AND e2.canonical_entity_id = intelligence.entity_profiles.canonical_entity_id
  );
DELETE FROM intelligence.entity_profiles WHERE domain_key = 'science-tech';

UPDATE intelligence.article_duplicate_sources a SET domain_key = 'politics-2'
WHERE domain_key = 'politics'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_duplicate_sources x
    WHERE x.domain_key = 'politics-2'
      AND x.canonical_article_id = a.canonical_article_id
      AND x.duplicate_url IS NOT DISTINCT FROM a.duplicate_url
      AND x.duplicate_source_domain IS NOT DISTINCT FROM a.duplicate_source_domain
      AND x.duplicate_title IS NOT DISTINCT FROM a.duplicate_title
  );
DELETE FROM intelligence.article_duplicate_sources WHERE domain_key = 'politics';

UPDATE intelligence.article_duplicate_sources a SET domain_key = 'finance-2'
WHERE domain_key = 'finance'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_duplicate_sources x
    WHERE x.domain_key = 'finance-2'
      AND x.canonical_article_id = a.canonical_article_id
      AND x.duplicate_url IS NOT DISTINCT FROM a.duplicate_url
      AND x.duplicate_source_domain IS NOT DISTINCT FROM a.duplicate_source_domain
      AND x.duplicate_title IS NOT DISTINCT FROM a.duplicate_title
  );
DELETE FROM intelligence.article_duplicate_sources WHERE domain_key = 'finance';

UPDATE intelligence.article_duplicate_sources a SET domain_key = 'artificial-intelligence'
WHERE domain_key = 'science-tech'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.article_duplicate_sources x
    WHERE x.domain_key = 'artificial-intelligence'
      AND x.canonical_article_id = a.canonical_article_id
      AND x.duplicate_url IS NOT DISTINCT FROM a.duplicate_url
      AND x.duplicate_source_domain IS NOT DISTINCT FROM a.duplicate_source_domain
      AND x.duplicate_title IS NOT DISTINCT FROM a.duplicate_title
  );
DELETE FROM intelligence.article_duplicate_sources WHERE domain_key = 'science-tech';

UPDATE intelligence.claim_subject_gap_catalog a SET domain_key = 'politics-2'
WHERE domain_key = 'politics'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.claim_subject_gap_catalog x
    WHERE x.domain_key = 'politics-2' AND x.subject_norm = a.subject_norm
  );
DELETE FROM intelligence.claim_subject_gap_catalog WHERE domain_key = 'politics';

UPDATE intelligence.claim_subject_gap_catalog a SET domain_key = 'finance-2'
WHERE domain_key = 'finance'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.claim_subject_gap_catalog x
    WHERE x.domain_key = 'finance-2' AND x.subject_norm = a.subject_norm
  );
DELETE FROM intelligence.claim_subject_gap_catalog WHERE domain_key = 'finance';

UPDATE intelligence.claim_subject_gap_catalog a SET domain_key = 'artificial-intelligence'
WHERE domain_key = 'science-tech'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.claim_subject_gap_catalog x
    WHERE x.domain_key = 'artificial-intelligence' AND x.subject_norm = a.subject_norm
  );
DELETE FROM intelligence.claim_subject_gap_catalog WHERE domain_key = 'science-tech';

UPDATE intelligence.content_refinement_queue a SET domain_key = 'politics-2'
WHERE domain_key = 'politics'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.content_refinement_queue x
    WHERE x.domain_key = 'politics-2'
      AND x.storyline_id = a.storyline_id
      AND x.job_type IS NOT DISTINCT FROM a.job_type
  );
DELETE FROM intelligence.content_refinement_queue WHERE domain_key = 'politics';

UPDATE intelligence.content_refinement_queue a SET domain_key = 'finance-2'
WHERE domain_key = 'finance'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.content_refinement_queue x
    WHERE x.domain_key = 'finance-2'
      AND x.storyline_id = a.storyline_id
      AND x.job_type IS NOT DISTINCT FROM a.job_type
  );
DELETE FROM intelligence.content_refinement_queue WHERE domain_key = 'finance';

UPDATE intelligence.content_refinement_queue a SET domain_key = 'artificial-intelligence'
WHERE domain_key = 'science-tech'
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.content_refinement_queue x
    WHERE x.domain_key = 'artificial-intelligence'
      AND x.storyline_id = a.storyline_id
      AND x.job_type IS NOT DISTINCT FROM a.job_type
  );
DELETE FROM intelligence.content_refinement_queue WHERE domain_key = 'science-tech';

UPDATE intelligence.narrative_threads SET domain_key = 'politics-2' WHERE domain_key = 'politics';
UPDATE intelligence.narrative_threads SET domain_key = 'finance-2' WHERE domain_key = 'finance';
UPDATE intelligence.narrative_threads SET domain_key = 'artificial-intelligence' WHERE domain_key = 'science-tech';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'intelligence' AND table_name = 'legislative_article_scans'
  ) THEN
    UPDATE intelligence.legislative_article_scans SET domain_key = 'politics-2' WHERE domain_key = 'politics';
    UPDATE intelligence.legislative_article_scans SET domain_key = 'finance-2' WHERE domain_key = 'finance';
    UPDATE intelligence.legislative_article_scans SET domain_key = 'artificial-intelligence' WHERE domain_key = 'science-tech';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'intelligence' AND table_name = 'legislative_references'
  ) THEN
    UPDATE intelligence.legislative_references lr SET domain_key = 'politics-2'
    WHERE domain_key = 'politics'
      AND NOT EXISTS (
        SELECT 1 FROM intelligence.legislative_references x
        WHERE x.domain_key = 'politics-2' AND x.article_id = lr.article_id
      );
    DELETE FROM intelligence.legislative_references WHERE domain_key = 'politics';

    UPDATE intelligence.legislative_references lr SET domain_key = 'finance-2'
    WHERE domain_key = 'finance'
      AND NOT EXISTS (
        SELECT 1 FROM intelligence.legislative_references x
        WHERE x.domain_key = 'finance-2' AND x.article_id = lr.article_id
      );
    DELETE FROM intelligence.legislative_references WHERE domain_key = 'finance';

    UPDATE intelligence.legislative_references lr SET domain_key = 'artificial-intelligence'
    WHERE domain_key = 'science-tech'
      AND NOT EXISTS (
        SELECT 1 FROM intelligence.legislative_references x
        WHERE x.domain_key = 'artificial-intelligence' AND x.article_id = lr.article_id
      );
    DELETE FROM intelligence.legislative_references WHERE domain_key = 'science-tech';
  END IF;
END $$;

-- tracked_events.domain_keys: text[] — replace tokens (may appear multiple times)
UPDATE intelligence.tracked_events
SET domain_keys =
  array_replace(
    array_replace(
      array_replace(
        array_replace(
          COALESCE(domain_keys, '{}'::text[]),
          'politics'::text,
          'politics-2'::text
        ),
        'finance'::text,
        'finance-2'::text
      ),
      'science-tech'::text,
      'artificial-intelligence'::text
    ),
    'science_tech'::text,
    'artificial_intelligence'::text
  )
WHERE domain_keys && ARRAY['politics', 'finance', 'science-tech', 'science_tech']::text[];

-- storyline_rag_context if present
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'intelligence' AND table_name = 'storyline_rag_context'
  ) THEN
    UPDATE intelligence.storyline_rag_context SET domain_key = 'politics-2' WHERE domain_key = 'politics';
    UPDATE intelligence.storyline_rag_context SET domain_key = 'finance-2' WHERE domain_key = 'finance';
    UPDATE intelligence.storyline_rag_context SET domain_key = 'artificial-intelligence' WHERE domain_key = 'science-tech';
  END IF;
END $$;

-- ml_processing_queue: schema_name column (migration 190)
UPDATE public.ml_processing_queue SET schema_name = 'politics_2' WHERE schema_name = 'politics';
UPDATE public.ml_processing_queue SET schema_name = 'finance_2' WHERE schema_name = 'finance';
UPDATE public.ml_processing_queue SET schema_name = 'artificial_intelligence' WHERE schema_name = 'science_tech';

-- Deactivate legacy domain registry rows (schemas may still exist for archival dumps)
UPDATE public.domains SET is_active = false
WHERE domain_key IN ('politics', 'finance', 'science-tech');

COMMIT;
