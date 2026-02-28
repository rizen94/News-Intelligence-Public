-- Migration 137: Banned topics per domain
-- Allows manual banning of vague or unhelpful topics (e.g. "truth social post", "on friday", "last week")
-- Banned topics are excluded from big picture, word cloud, and trending views

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT domains.schema_name FROM domains WHERE is_active = true
    LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.banned_topics (
                id SERIAL PRIMARY KEY,
                topic_name VARCHAR(300) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                reason VARCHAR(500),
                UNIQUE(topic_name)
            )', schema_name);

        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%I_banned_topics_topic_name ON %I.banned_topics(topic_name);
        ', schema_name, schema_name);

        RAISE NOTICE 'Created banned_topics table for schema: %', schema_name;
    END LOOP;
END $$;
