-- Migration 166: Add assignment_context and model_version to article_topic_assignments if missing.
-- Fixes: "column assignment_context of relation article_topic_assignments does not exist"
-- when topic clustering runs (topic_clustering_service inserts these columns).
-- Some DBs may have had the table created without these columns.

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT unnest(ARRAY['politics', 'finance', 'science_tech'])
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = schema_name AND table_name = 'article_topic_assignments'
        ) THEN
            -- assignment_context: JSONB context used for assignment (keywords, entities, etc.)
            EXECUTE format(
                'ALTER TABLE %I.article_topic_assignments ADD COLUMN IF NOT EXISTS assignment_context JSONB DEFAULT ''{}''',
                schema_name
            );
            -- model_version: which model/version made the assignment
            EXECUTE format(
                'ALTER TABLE %I.article_topic_assignments ADD COLUMN IF NOT EXISTS model_version VARCHAR(50)',
                schema_name
            );
            RAISE NOTICE 'Added assignment_context/model_version to %.article_topic_assignments (if missing)', schema_name;
        END IF;
    END LOOP;
END $$;
