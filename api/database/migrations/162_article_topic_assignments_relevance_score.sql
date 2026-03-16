-- Migration 162: Ensure article_topic_assignments has relevance_score in all domain schemas.
-- Fixes: "column relevance_score of relation article_topic_assignments does not exist"
-- when topic clustering runs. Some DBs may have had the table created without this column.

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
            EXECUTE format(
                'ALTER TABLE %I.article_topic_assignments ADD COLUMN IF NOT EXISTS relevance_score DECIMAL(3,2) DEFAULT 0.5',
                schema_name
            );
            RAISE NOTICE 'Added relevance_score to %.article_topic_assignments (if missing)', schema_name;
        END IF;
    END LOOP;
END $$;
