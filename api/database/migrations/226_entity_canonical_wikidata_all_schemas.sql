-- Migration 226: wikidata_qid on every domain entity_canonical (not only public.domains rows)
-- Migration 222 iterated public.domains; when schema_name is stale (e.g. politics_2 while
-- politics holds live data), primary silos miss the column. This backfills all silos.

BEGIN;

DO $$
DECLARE
  r RECORD;
  stmt TEXT;
BEGIN
  FOR r IN
    SELECT DISTINCT table_schema AS schema_name
    FROM information_schema.tables
    WHERE table_name = 'entity_canonical'
      AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
      AND table_schema NOT LIKE 'pg_%'
  LOOP
    stmt := format(
      $sql$
      ALTER TABLE %I.entity_canonical
          ADD COLUMN IF NOT EXISTS wikidata_qid text;
      CREATE INDEX IF NOT EXISTS idx_%I_entity_canonical_wikidata_qid
          ON %I.entity_canonical (wikidata_qid)
          WHERE wikidata_qid IS NOT NULL AND wikidata_qid <> '';
      $sql$,
      r.schema_name, r.schema_name, r.schema_name
    );
    EXECUTE stmt;
  END LOOP;
END $$;

COMMIT;
