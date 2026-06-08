-- Migration 221: Provenance timestamps (event_date, ingestion_date, vintage_date)
-- Phase 0 — NI Longitudinal Intelligence / chronological accuracy doctrine.
-- See docs/CHRONOLOGICAL_ACCURACY_DOCTRINE.md

BEGIN;

-- intelligence.contexts
ALTER TABLE intelligence.contexts
    ADD COLUMN IF NOT EXISTS event_date timestamptz,
    ADD COLUMN IF NOT EXISTS ingestion_date timestamptz,
    ADD COLUMN IF NOT EXISTS vintage_date timestamptz;

UPDATE intelligence.contexts
SET ingestion_date = COALESCE(ingestion_date, created_at),
    event_date = COALESCE(event_date, created_at)
WHERE ingestion_date IS NULL OR event_date IS NULL;

-- intelligence.extracted_claims
ALTER TABLE intelligence.extracted_claims
    ADD COLUMN IF NOT EXISTS event_date timestamptz,
    ADD COLUMN IF NOT EXISTS ingestion_date timestamptz,
    ADD COLUMN IF NOT EXISTS vintage_date timestamptz;

UPDATE intelligence.extracted_claims ec
SET ingestion_date = COALESCE(ec.ingestion_date, ec.created_at),
    event_date = COALESCE(
        ec.event_date,
        (SELECT c.event_date FROM intelligence.contexts c WHERE c.id = ec.context_id),
        ec.created_at
    )
WHERE ec.ingestion_date IS NULL OR ec.event_date IS NULL;

-- intelligence.versioned_facts (valid_from remains; event_date mirrors for API uniformity)
ALTER TABLE intelligence.versioned_facts
    ADD COLUMN IF NOT EXISTS event_date timestamptz,
    ADD COLUMN IF NOT EXISTS ingestion_date timestamptz,
    ADD COLUMN IF NOT EXISTS vintage_date timestamptz;

UPDATE intelligence.versioned_facts vf
SET event_date = COALESCE(vf.event_date, vf.valid_from),
    ingestion_date = COALESCE(
        vf.ingestion_date,
        vf.created_at,
        vf.valid_from,
        NOW()
    )
WHERE vf.event_date IS NULL OR vf.ingestion_date IS NULL;

-- public.chronological_events
ALTER TABLE public.chronological_events
    ADD COLUMN IF NOT EXISTS event_date timestamptz,
    ADD COLUMN IF NOT EXISTS ingestion_date timestamptz,
    ADD COLUMN IF NOT EXISTS vintage_date timestamptz;

UPDATE public.chronological_events ce
SET event_date = COALESCE(ce.event_date, ce.actual_event_date, ce.created_at),
    ingestion_date = COALESCE(ce.ingestion_date, ce.created_at)
WHERE ce.event_date IS NULL OR ce.ingestion_date IS NULL;

-- Per-domain articles
DO $$
DECLARE
  r RECORD;
  stmt TEXT;
BEGIN
  FOR r IN
    SELECT DISTINCT schema_name
    FROM public.domains
    WHERE schema_name IS NOT NULL AND schema_name <> ''
  LOOP
    stmt := format(
      $sql$
      ALTER TABLE %I.articles
          ADD COLUMN IF NOT EXISTS event_date timestamptz,
          ADD COLUMN IF NOT EXISTS ingestion_date timestamptz,
          ADD COLUMN IF NOT EXISTS vintage_date timestamptz;
      UPDATE %I.articles
      SET ingestion_date = COALESCE(ingestion_date, created_at),
          event_date = COALESCE(event_date, published_at, created_at)
      WHERE ingestion_date IS NULL OR event_date IS NULL;
      $sql$,
      r.schema_name,
      r.schema_name
    );
    EXECUTE stmt;
  END LOOP;
END $$;

COMMENT ON COLUMN intelligence.contexts.event_date IS
    'When the underlying news event occurred (usually article published_at).';
COMMENT ON COLUMN intelligence.contexts.ingestion_date IS
    'When NI first stored this context row.';
COMMENT ON COLUMN intelligence.contexts.vintage_date IS
    'When the source last revised content (nullable until enrichment).';

COMMIT;
