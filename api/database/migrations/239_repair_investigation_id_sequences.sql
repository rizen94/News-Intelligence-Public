-- Repair investigation_* id sequences after DROP SCHEMA nri CASCADE (defaults referenced nri sequences).
-- Run immediately after 238_drop_nri_schema.sql if CASCADE removed column defaults.

BEGIN;

DO $$
DECLARE
  tbl text;
  seq_name text;
  max_id bigint;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'investigation_resolved_mentions',
    'investigation_parked_resolution',
    'investigation_loop_run',
    'investigation_provisional_mints'
  ]
  LOOP
    seq_name := format('intelligence.%I_id_seq', tbl);
    EXECUTE format('CREATE SEQUENCE IF NOT EXISTS %s', seq_name);
    EXECUTE format(
      'SELECT COALESCE(MAX(id), 0) FROM intelligence.%I',
      tbl
    ) INTO max_id;
    EXECUTE format('SELECT setval(%L, %s, true)', seq_name, GREATEST(max_id, 1));
    EXECUTE format(
      'ALTER TABLE intelligence.%I ALTER COLUMN id SET DEFAULT nextval(%L)',
      tbl,
      seq_name
    );
    EXECUTE format(
      'ALTER SEQUENCE %s OWNED BY intelligence.%I.id',
      seq_name,
      tbl
    );
  END LOOP;
END $$;

COMMIT;
