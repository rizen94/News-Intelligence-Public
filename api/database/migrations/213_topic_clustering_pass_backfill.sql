-- Migration 213: Backfill metadata.pipeline.topic_clustering.last_pass_at for articles that already
-- have topic assignments, so Monitor "unprocessed" counts match "never attempted" after enabling
-- pass-marker semantics (see TOPIC_CLUSTERING_BACKLOG_USE_PASS_MARKER).

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
      UPDATE %I.articles a
      SET metadata = jsonb_set(
        COALESCE(metadata, '{}'::jsonb),
        '{pipeline}',
        COALESCE(metadata->'pipeline', '{}'::jsonb)
          || jsonb_build_object(
               'topic_clustering',
               COALESCE(metadata->'pipeline'->'topic_clustering', '{}'::jsonb)
                 || jsonb_build_object(
                      'last_pass_at', to_jsonb(NOW()::text),
                      'backfilled', 'true'::jsonb
                    )
             ),
        true
      )
      WHERE EXISTS (
        SELECT 1 FROM %I.article_topic_assignments ata
        WHERE ata.article_id = a.id
      )
        AND (metadata->'pipeline'->'topic_clustering'->>'last_pass_at') IS NULL
      $sql$,
      r.schema_name,
      r.schema_name
    );
    BEGIN
      EXECUTE stmt;
    EXCEPTION
      WHEN undefined_table THEN
        RAISE NOTICE '213 skip schema % (missing tables)', r.schema_name;
    END;
  END LOOP;
END $$;

COMMIT;
