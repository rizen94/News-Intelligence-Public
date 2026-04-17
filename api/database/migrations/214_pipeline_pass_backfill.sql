-- Migration 214: Backfill metadata.pipeline.<phase>.last_pass_at for articles/contexts that already
-- satisfy completion signals, so Monitor pending counts align with pass-marker semantics
-- (PIPELINE_BACKLOG_USE_PASS_MARKERS, default true).

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
    -- entity_extraction: rows with stored article_entities
    stmt := format(
      $sql$
      UPDATE %I.articles a
      SET metadata = jsonb_set(
        COALESCE(metadata, '{}'::jsonb),
        '{pipeline}',
        COALESCE(metadata->'pipeline', '{}'::jsonb)
          || jsonb_build_object(
               'entity_extraction',
               COALESCE(metadata->'pipeline'->'entity_extraction', '{}'::jsonb)
                 || jsonb_build_object(
                      'last_pass_at', to_jsonb(NOW()::text),
                      'backfilled', 'true'::jsonb
                    )
             ),
        true
      )
      WHERE EXISTS (
        SELECT 1 FROM %I.article_entities ae WHERE ae.article_id = a.id
      )
        AND (a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_pass_at') IS NULL
      $sql$,
      r.schema_name,
      r.schema_name
    );
    BEGIN
      EXECUTE stmt;
    EXCEPTION
      WHEN undefined_table THEN
        RAISE NOTICE '214 skip entity_extraction schema % (missing tables)', r.schema_name;
    END;

    -- sentiment_analysis: scored articles
    stmt := format(
      $sql$
      UPDATE %I.articles a
      SET metadata = jsonb_set(
        COALESCE(metadata, '{}'::jsonb),
        '{pipeline}',
        COALESCE(metadata->'pipeline', '{}'::jsonb)
          || jsonb_build_object(
               'sentiment_analysis',
               COALESCE(metadata->'pipeline'->'sentiment_analysis', '{}'::jsonb)
                 || jsonb_build_object(
                      'last_pass_at', to_jsonb(NOW()::text),
                      'backfilled', 'true'::jsonb
                    )
             ),
        true
      )
      WHERE a.sentiment_score IS NOT NULL
        AND (a.metadata::jsonb->'pipeline'->'sentiment_analysis'->>'last_pass_at') IS NULL
      $sql$,
      r.schema_name
    );
    BEGIN
      EXECUTE stmt;
    EXCEPTION
      WHEN undefined_table THEN
        RAISE NOTICE '214 skip sentiment schema %', r.schema_name;
    END;

    -- event_extraction (v5): timeline_processed
    stmt := format(
      $sql$
      UPDATE %I.articles a
      SET metadata = jsonb_set(
        COALESCE(metadata, '{}'::jsonb),
        '{pipeline}',
        COALESCE(metadata->'pipeline', '{}'::jsonb)
          || jsonb_build_object(
               'event_extraction',
               COALESCE(metadata->'pipeline'->'event_extraction', '{}'::jsonb)
                 || jsonb_build_object(
                      'last_pass_at', to_jsonb(NOW()::text),
                      'backfilled', 'true'::jsonb
                    )
             ),
        true
      )
      WHERE a.timeline_processed = true
        AND (a.metadata::jsonb->'pipeline'->'event_extraction'->>'last_pass_at') IS NULL
      $sql$,
      r.schema_name
    );
    BEGIN
      EXECUTE stmt;
    EXCEPTION
      WHEN undefined_table THEN
        RAISE NOTICE '214 skip event_extraction schema %', r.schema_name;
    END;

    -- metadata_enrichment: enrichment_done
    stmt := format(
      $sql$
      UPDATE %I.articles a
      SET metadata = jsonb_set(
        COALESCE(metadata, '{}'::jsonb),
        '{pipeline}',
        COALESCE(metadata->'pipeline', '{}'::jsonb)
          || jsonb_build_object(
               'metadata_enrichment',
               COALESCE(metadata->'pipeline'->'metadata_enrichment', '{}'::jsonb)
                 || jsonb_build_object(
                      'last_pass_at', to_jsonb(NOW()::text),
                      'backfilled', 'true'::jsonb
                    )
             ),
        true
      )
      WHERE (a.metadata->>'enrichment_done') = 'true'
        AND (a.metadata::jsonb->'pipeline'->'metadata_enrichment'->>'last_pass_at') IS NULL
      $sql$,
      r.schema_name
    );
    BEGIN
      EXECUTE stmt;
    EXCEPTION
      WHEN undefined_table THEN
        RAISE NOTICE '214 skip metadata_enrichment schema %', r.schema_name;
    END;

    -- storyline_discovery: on any storyline
    stmt := format(
      $sql$
      UPDATE %I.articles a
      SET metadata = jsonb_set(
        COALESCE(metadata, '{}'::jsonb),
        '{pipeline}',
        COALESCE(metadata->'pipeline', '{}'::jsonb)
          || jsonb_build_object(
               'storyline_discovery',
               COALESCE(metadata->'pipeline'->'storyline_discovery', '{}'::jsonb)
                 || jsonb_build_object(
                      'last_pass_at', to_jsonb(NOW()::text),
                      'backfilled', 'true'::jsonb
                    )
             ),
        true
      )
      WHERE EXISTS (
        SELECT 1 FROM %I.storyline_articles sa WHERE sa.article_id = a.id
      )
        AND (a.metadata::jsonb->'pipeline'->'storyline_discovery'->>'last_pass_at') IS NULL
      $sql$,
      r.schema_name,
      r.schema_name
    );
    BEGIN
      EXECUTE stmt;
    EXCEPTION
      WHEN undefined_table THEN
        RAISE NOTICE '214 skip storyline_discovery schema %', r.schema_name;
    END;
  END LOOP;
END $$;

-- intelligence.contexts: claim_extraction pass where claims exist
UPDATE intelligence.contexts c
SET metadata = jsonb_set(
  COALESCE(c.metadata::jsonb, '{}'::jsonb),
  '{pipeline}',
  COALESCE(c.metadata::jsonb->'pipeline', '{}'::jsonb)
    || jsonb_build_object(
         'claim_extraction',
         COALESCE(c.metadata::jsonb->'pipeline'->'claim_extraction', '{}'::jsonb)
           || jsonb_build_object(
                'last_pass_at', to_jsonb(NOW()::text),
                'backfilled', 'true'::jsonb
              )
       ),
  true
)
WHERE EXISTS (SELECT 1 FROM intelligence.extracted_claims ec WHERE ec.context_id = c.id)
  AND ((COALESCE(c.metadata::jsonb, '{}'::jsonb))->'pipeline'->'claim_extraction'->>'last_pass_at') IS NULL;

-- intelligence.contexts: event_tracking pass where already linked in a chronicle
UPDATE intelligence.contexts c
SET metadata = jsonb_set(
  COALESCE(c.metadata::jsonb, '{}'::jsonb),
  '{pipeline}',
  COALESCE(c.metadata::jsonb->'pipeline', '{}'::jsonb)
    || jsonb_build_object(
         'event_tracking',
         COALESCE(c.metadata::jsonb->'pipeline'->'event_tracking', '{}'::jsonb)
           || jsonb_build_object(
                'last_pass_at', to_jsonb(NOW()::text),
                'backfilled', 'true'::jsonb
              )
       ),
  true
)
WHERE EXISTS (
    SELECT 1 FROM intelligence.event_chronicles ec,
    LATERAL jsonb_array_elements(ec.developments) AS dev
    WHERE (dev->>'context_id')::int = c.id
  )
  AND ((COALESCE(c.metadata::jsonb, '{}'::jsonb))->'pipeline'->'event_tracking'->>'last_pass_at') IS NULL;

COMMIT;
