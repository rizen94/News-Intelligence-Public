-- topic_extraction_queue for domains that ingest RSS but never received migration 130/206 pattern.

DO $$
DECLARE
    sch TEXT;
BEGIN
    FOREACH sch IN ARRAY ARRAY['legal', 'medicine', 'artificial_intelligence'] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = sch AND table_name = 'topic_extraction_queue'
        ) THEN
            EXECUTE format($SQL$
                CREATE TABLE %I.topic_extraction_queue (
                    id SERIAL PRIMARY KEY,
                    article_id INTEGER NOT NULL REFERENCES %I.articles(id) ON DELETE CASCADE,
                    status VARCHAR(20) DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
                    priority INTEGER DEFAULT 2 CHECK (priority >= 1 AND priority <= 4),
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 10,
                    last_attempt_at TIMESTAMPTZ,
                    next_retry_at TIMESTAMPTZ,
                    error_message TEXT,
                    last_error TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    UNIQUE(article_id)
                )
            $SQL$, sch, sch);
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS idx_%I_topic_queue_status ON %I.topic_extraction_queue(status)',
                sch, sch
            );
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS idx_%I_topic_queue_priority ON %I.topic_extraction_queue(priority DESC, created_at ASC)',
                sch, sch
            );
            RAISE NOTICE 'Created %.topic_extraction_queue', sch;
        END IF;
    END LOOP;
END $$;
