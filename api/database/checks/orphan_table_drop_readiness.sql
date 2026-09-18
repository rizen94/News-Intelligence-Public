-- Read-only readiness checks before migration 307 drops the two orphaned intelligence tables.
-- Nothing here writes. Run on Widow against news_intel, admin port (direct Postgres :5432).
--
--   psql -h 127.0.0.1 -p 5432 -U newsapp -d news_intel -f api/database/checks/orphan_table_drop_readiness.sql
--
-- Proceed only when: row counts are 0, no dependents, and no recent writes.
-- Context and the decision record: docs/ORPHANED_DB_SURFACES.md

\echo '=== 1. Do the tables still exist? ==='
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'intelligence'
  AND table_name IN ('unseeded_claims_parking_lot', 'entity_alias_merge_log')
ORDER BY table_name;

\echo ''
\echo '=== 2. Row counts (must be 0 to drop) ==='
SELECT 'unseeded_claims_parking_lot' AS table_name, count(*) AS row_count
FROM intelligence.unseeded_claims_parking_lot
UNION ALL
SELECT 'entity_alias_merge_log', count(*)
FROM intelligence.entity_alias_merge_log;

\echo ''
\echo '=== 3. Most recent write (NULL/empty = never written) ==='
SELECT 'unseeded_claims_parking_lot' AS table_name,
       max(extracted_at) AS newest_row
FROM intelligence.unseeded_claims_parking_lot
UNION ALL
SELECT 'entity_alias_merge_log',
       max(merged_at)
FROM intelligence.entity_alias_merge_log;

\echo ''
\echo '=== 4. Write activity since last stats reset (n_tup_ins/upd/del must be 0) ==='
SELECT relname,
       n_tup_ins,
       n_tup_upd,
       n_tup_del,
       n_live_tup,
       last_autovacuum,
       last_analyze
FROM pg_stat_all_tables
WHERE schemaname = 'intelligence'
  AND relname IN ('unseeded_claims_parking_lot', 'entity_alias_merge_log')
ORDER BY relname;

\echo ''
\echo '=== 5. Inbound foreign keys (must be empty) ==='
SELECT c.conname,
       src.relname  AS referencing_table,
       ref.relname  AS referenced_table
FROM pg_constraint c
JOIN pg_class src        ON src.oid = c.conrelid
JOIN pg_class ref        ON ref.oid = c.confrelid
JOIN pg_namespace refn   ON refn.oid = ref.relnamespace
WHERE c.contype = 'f'
  AND refn.nspname = 'intelligence'
  AND ref.relname IN ('unseeded_claims_parking_lot', 'entity_alias_merge_log');

\echo ''
\echo '=== 6. Views / matviews depending on them (must be empty) ==='
SELECT DISTINCT vn.nspname AS view_schema,
       v.relname          AS view_name,
       v.relkind          AS kind,
       t.relname          AS depends_on
FROM pg_depend d
JOIN pg_rewrite r      ON r.oid = d.objid
JOIN pg_class v        ON v.oid = r.ev_class
JOIN pg_namespace vn   ON vn.oid = v.relnamespace
JOIN pg_class t        ON t.oid = d.refobjid
JOIN pg_namespace tn   ON tn.oid = t.relnamespace
WHERE tn.nspname = 'intelligence'
  AND t.relname IN ('unseeded_claims_parking_lot', 'entity_alias_merge_log')
  AND v.relkind IN ('v', 'm')
  AND v.relname <> t.relname;

\echo ''
\echo '=== 7. Other dependent objects: triggers, sequences, publications ==='
SELECT tgname AS trigger_name, c.relname AS on_table
FROM pg_trigger tg
JOIN pg_class c      ON c.oid = tg.tgrelid
JOIN pg_namespace n  ON n.oid = c.relnamespace
WHERE NOT tg.tgisinternal
  AND n.nspname = 'intelligence'
  AND c.relname IN ('unseeded_claims_parking_lot', 'entity_alias_merge_log');

SELECT pubname, schemaname, tablename
FROM pg_publication_tables
WHERE schemaname = 'intelligence'
  AND tablename IN ('unseeded_claims_parking_lot', 'entity_alias_merge_log');

\echo ''
\echo '=== 8. The interim markers from migration 306 should be present ==='
SELECT c.relname,
       obj_description(c.oid, 'pg_class') AS table_comment
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'intelligence'
  AND c.relname IN ('unseeded_claims_parking_lot', 'entity_alias_merge_log')
ORDER BY c.relname;

\echo ''
\echo '=== 9. Sanity: confirm the *editorial* parking lot is a different table and is in use ==='
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'intelligence'
  AND table_name LIKE '%parking%'
ORDER BY table_name;

\echo ''
\echo 'If 2 shows 0 rows, and 5/6/7 are all empty, migration 307 will drop them:'
\echo '  PGOPTIONS="-c ni.allow_orphan_table_drop=1" psql ... -f api/database/migrations/307_drop_orphaned_intelligence_tables.sql'
\echo 'Migration 307 re-checks all of this itself and refuses if anything changed.'
