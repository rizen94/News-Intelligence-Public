-- migration_add_wiki_status.sql
-- Adds wiki_status + wiki_checked_at to entity_canonical in ALL domain schemas.
-- Safe to re-run (IF NOT EXISTS).

DO $$
DECLARE
    s TEXT;
    row_count BIGINT;
BEGIN
    FOR s IN
        SELECT DISTINCT table_schema
        FROM information_schema.tables
        WHERE table_name = 'entity_canonical'
          AND table_schema NOT IN ('information_schema', 'pg_catalog')
    LOOP
        -- Add columns
        EXECUTE format(
            'ALTER TABLE %I.entity_canonical ADD COLUMN IF NOT EXISTS wiki_status VARCHAR(20) DEFAULT ''pending''',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.entity_canonical ADD COLUMN IF NOT EXISTS wiki_checked_at TIMESTAMPTZ',
            s
        );

        -- Backfill: entities that already have a wikipedia_page_id are 'found'
        EXECUTE format(
            'UPDATE %I.entity_canonical SET wiki_status = ''found'', wiki_checked_at = NOW() WHERE wikipedia_page_id IS NOT NULL AND (wiki_status IS NULL OR wiki_status = ''pending'')',
            s
        );
        GET DIAGNOSTICS row_count = ROW_COUNT;
        RAISE NOTICE 'Schema %: % entities marked as found (had wikipedia_page_id)', s, row_count;

        -- Index for the enrichment query pattern
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%s_ec_wiki_status ON %I.entity_canonical (wiki_status) WHERE wiki_status = ''pending''',
            replace(s, '-', '_'), s
        );
    END LOOP;
END $$;

-- Also add wiki enrichment tracking to intelligence.entity_profiles metadata
-- (No schema change needed — metadata is already JSONB, we just query it differently)

-- Verify
SELECT table_schema, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'entity_canonical'
  AND column_name IN ('wiki_status', 'wiki_checked_at')
ORDER BY table_schema, column_name;
