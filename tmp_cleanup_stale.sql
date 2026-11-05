-- Clean up stale _idx1 duplicate enrichment indexes from repeated migration runs
DO $$
DECLARE
  rec RECORD;
BEGIN
  FOR rec IN
    SELECT indexrelid::regclass as index_name, indrelid::regclass as table_name
    FROM pg_stat_user_indexes
    WHERE indexrelname LIKE '%_idx1' AND indexrelname NOT LIKE 'idx%'
      AND indrelid::regclass::text = 'articles'
  LOOP
    EXECUTE format('DROP INDEX IF EXISTS %I', rec.index_name);
    RAISE NOTICE 'Dropped stale index: % on table: %', rec.index_name, rec.table_name;
  END LOOP;
END $$;
