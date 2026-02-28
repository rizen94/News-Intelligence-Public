-- Migration 129: Add topic_keywords table to domain schemas
-- Creates topic_keywords table in each domain schema for word cloud data storage
-- This enables incremental word cloud improvements over time

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    -- Loop through all active domain schemas
    FOR schema_name IN SELECT domains.schema_name FROM domains WHERE is_active = true
    LOOP
        -- Create topic_keywords table in domain schema
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.topic_keywords (
                id SERIAL PRIMARY KEY,
                topic_cluster_id INTEGER NOT NULL REFERENCES %I.topic_clusters(id) ON DELETE CASCADE,
                
                -- Keyword Information
                keyword VARCHAR(200) NOT NULL,
                keyword_type VARCHAR(50) DEFAULT ''general'' CHECK (keyword_type IN (
                    ''general'', ''entity'', ''location'', ''organization'', ''person'', ''concept''
                )),
                
                -- Frequency and Importance
                frequency_count INTEGER DEFAULT 1,
                importance_score DECIMAL(3,2) DEFAULT 0.0,
                tf_idf_score DECIMAL(6,4) DEFAULT 0.0,
                
                -- Metadata
                first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB DEFAULT ''{}'',
                
                -- Constraints
                CONSTRAINT chk_keyword_scores CHECK (
                    importance_score >= 0.0 AND importance_score <= 1.0 AND
                    tf_idf_score >= 0.0
                ),
                UNIQUE(topic_cluster_id, keyword)
            )', schema_name, schema_name);
        
        -- Create indexes for performance
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%I_topic_keywords_cluster_id ON %I.topic_keywords(topic_cluster_id);
            CREATE INDEX IF NOT EXISTS idx_%I_topic_keywords_frequency ON %I.topic_keywords(frequency_count);
            CREATE INDEX IF NOT EXISTS idx_%I_topic_keywords_importance ON %I.topic_keywords(importance_score);
            CREATE INDEX IF NOT EXISTS idx_%I_topic_keywords_keyword ON %I.topic_keywords(keyword);
        ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
        
        RAISE NOTICE 'Created topic_keywords table and indexes for schema: %', schema_name;
    END LOOP;
END $$;

