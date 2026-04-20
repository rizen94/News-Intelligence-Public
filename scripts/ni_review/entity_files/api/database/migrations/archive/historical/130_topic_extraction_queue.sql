-- Migration 130: Topic Extraction Queue System
-- Creates queue for articles that need LLM-based topic extraction
-- Ensures articles are processed when LLM becomes available

-- Create topic extraction queue table (domain-specific)
DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT domains.schema_name FROM domains WHERE is_active = true
    LOOP
        -- Create topic extraction queue table
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.topic_extraction_queue (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES %I.articles(id) ON DELETE CASCADE,
                
                -- Queue metadata
                status VARCHAR(20) DEFAULT ''pending'' CHECK (status IN (''pending'', ''processing'', ''completed'', ''failed'')),
                priority INTEGER DEFAULT 2 CHECK (priority >= 1 AND priority <= 4),
                
                -- Retry management
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 10,
                last_attempt_at TIMESTAMP WITH TIME ZONE,
                next_retry_at TIMESTAMP WITH TIME ZONE,
                
                -- Error tracking
                error_message TEXT,
                last_error TEXT,
                
                -- Timestamps
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                
                -- Metadata
                metadata JSONB DEFAULT ''{}'',
                
                -- Constraints
                UNIQUE(article_id)  -- One queue entry per article
            )', schema_name, schema_name);
        
        -- Create indexes for performance
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%I_topic_queue_status ON %I.topic_extraction_queue(status);
            CREATE INDEX IF NOT EXISTS idx_%I_topic_queue_priority ON %I.topic_extraction_queue(priority DESC, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_%I_topic_queue_retry ON %I.topic_extraction_queue(next_retry_at) WHERE status = ''pending'';
            CREATE INDEX IF NOT EXISTS idx_%I_topic_queue_article ON %I.topic_extraction_queue(article_id);
        ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
        
        RAISE NOTICE 'Created topic_extraction_queue table and indexes for schema: %', schema_name;
    END LOOP;
END $$;

-- Create function to get next articles to process
CREATE OR REPLACE FUNCTION get_next_topic_extraction_batch(
    schema_name TEXT,
    batch_size INTEGER DEFAULT 10,
    max_retries INTEGER DEFAULT 10
) RETURNS TABLE (
    id INTEGER,
    article_id INTEGER,
    retry_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    EXECUTE format('
        SELECT tq.id, tq.article_id, tq.retry_count
        FROM %I.topic_extraction_queue tq
        WHERE tq.status = ''pending''
        AND tq.retry_count < %s
        AND (tq.next_retry_at IS NULL OR tq.next_retry_at <= NOW())
        ORDER BY tq.priority DESC, tq.created_at ASC
        LIMIT %s
        FOR UPDATE SKIP LOCKED
    ', schema_name, max_retries, batch_size);
END;
$$ LANGUAGE plpgsql;

