-- Database Scaling Optimizations
-- Implements partitioning, indexing, and cleanup policies for large-scale processing

-- Create partitioned tables for better performance with large datasets
-- Articles table partitioning by date
CREATE TABLE IF NOT EXISTS articles_partitioned (
    LIKE articles INCLUDING ALL
) PARTITION BY RANGE (published_date);

-- Create monthly partitions for articles (last 2 years)
DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE - INTERVAL '24 months');
    end_date DATE := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month');
    current_date DATE := start_date;
    partition_name TEXT;
BEGIN
    WHILE current_date < end_date LOOP
        partition_name := 'articles_' || TO_CHAR(current_date, 'YYYY_MM');
        
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF articles_partitioned
                       FOR VALUES FROM (%L) TO (%L)',
                       partition_name,
                       current_date,
                       current_date + INTERVAL '1 month');
        
        current_date := current_date + INTERVAL '1 month';
    END LOOP;
END $$;

-- Create indexes for better query performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_published_date_btree 
ON articles USING btree (published_date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_processing_status_btree 
ON articles USING btree (processing_status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_source_btree 
ON articles USING btree (source);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_category_btree 
ON articles USING btree (category);

-- Composite indexes for common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_status_date 
ON articles (processing_status, published_date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_source_date 
ON articles (source, published_date DESC);

-- Full-text search indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_title_gin 
ON articles USING gin (to_tsvector('english', title));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_content_gin 
ON articles USING gin (to_tsvector('english', content));

-- Timeline events partitioning
CREATE TABLE IF NOT EXISTS timeline_events_partitioned (
    LIKE timeline_events INCLUDING ALL
) PARTITION BY RANGE (event_date);

-- Create monthly partitions for timeline events
DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE - INTERVAL '12 months');
    end_date DATE := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month');
    current_date DATE := start_date;
    partition_name TEXT;
BEGIN
    WHILE current_date < end_date LOOP
        partition_name := 'timeline_events_' || TO_CHAR(current_date, 'YYYY_MM');
        
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF timeline_events_partitioned
                       FOR VALUES FROM (%L) TO (%L)',
                       partition_name,
                       current_date,
                       current_date + INTERVAL '1 month');
        
        current_date := current_date + INTERVAL '1 month';
    END LOOP;
END $$;

-- System monitoring table for scaling metrics
CREATE TABLE IF NOT EXISTS system_scaling_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_articles INTEGER DEFAULT 0,
    raw_articles INTEGER DEFAULT 0,
    processing_articles INTEGER DEFAULT 0,
    completed_articles INTEGER DEFAULT 0,
    failed_articles INTEGER DEFAULT 0,
    total_timeline_events INTEGER DEFAULT 0,
    active_storylines INTEGER DEFAULT 0,
    queue_size INTEGER DEFAULT 0,
    running_tasks INTEGER DEFAULT 0,
    database_size_bytes BIGINT DEFAULT 0,
    avg_processing_time_seconds DECIMAL(10,2) DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for scaling metrics queries
CREATE INDEX IF NOT EXISTS idx_system_scaling_metrics_timestamp 
ON system_scaling_metrics (timestamp DESC);

-- Article processing batches table for better batch management
CREATE TABLE IF NOT EXISTS article_processing_batches (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(255) UNIQUE NOT NULL,
    batch_type VARCHAR(50) NOT NULL, -- 'manual', 'scheduled', 'bulk_import'
    total_articles INTEGER NOT NULL,
    processed_articles INTEGER DEFAULT 0,
    failed_articles INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    priority INTEGER DEFAULT 2,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Index for batch management
CREATE INDEX IF NOT EXISTS idx_article_processing_batches_status 
ON article_processing_batches (status);

CREATE INDEX IF NOT EXISTS idx_article_processing_batches_created_at 
ON article_processing_batches (created_at DESC);

-- Batch articles mapping table
CREATE TABLE IF NOT EXISTS batch_articles (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(255) NOT NULL,
    article_id INTEGER NOT NULL,
    processing_order INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES article_processing_batches(batch_id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

-- Index for batch articles
CREATE INDEX IF NOT EXISTS idx_batch_articles_batch_id 
ON batch_articles (batch_id);

CREATE INDEX IF NOT EXISTS idx_batch_articles_article_id 
ON batch_articles (article_id);

-- Storage cleanup policies table
CREATE TABLE IF NOT EXISTS storage_cleanup_policies (
    id SERIAL PRIMARY KEY,
    policy_name VARCHAR(100) UNIQUE NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    retention_days INTEGER NOT NULL,
    cleanup_condition TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_run TIMESTAMP,
    last_cleaned_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default cleanup policies
INSERT INTO storage_cleanup_policies (policy_name, table_name, retention_days, cleanup_condition)
VALUES 
    ('old_raw_articles', 'articles', 30, 'processing_status = ''raw'' AND created_at < NOW() - INTERVAL ''30 days'''),
    ('old_failed_articles', 'articles', 7, 'processing_status = ''failed'' AND created_at < NOW() - INTERVAL ''7 days'''),
    ('old_timeline_events', 'timeline_events', 90, 'created_at < NOW() - INTERVAL ''90 days'''),
    ('old_ml_tasks', 'ml_task_queue', 14, 'status IN (''completed'', ''failed'') AND completed_at < NOW() - INTERVAL ''14 days'''),
    ('old_system_logs', 'system_logs', 30, 'created_at < NOW() - INTERVAL ''30 days''')
ON CONFLICT (policy_name) DO NOTHING;

-- Rate limiting table
CREATE TABLE IF NOT EXISTS rate_limiting (
    id SERIAL PRIMARY KEY,
    resource_type VARCHAR(50) NOT NULL, -- 'ml_processing', 'timeline_generation', 'api_calls'
    resource_key VARCHAR(255) NOT NULL, -- 'user_id', 'ip_address', 'global'
    request_count INTEGER DEFAULT 1,
    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    max_requests INTEGER NOT NULL,
    window_duration_seconds INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(resource_type, resource_key, window_start)
);

-- Index for rate limiting
CREATE INDEX IF NOT EXISTS idx_rate_limiting_resource 
ON rate_limiting (resource_type, resource_key, window_start);

-- Performance monitoring table
CREATE TABLE IF NOT EXISTS performance_monitoring (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL,
    operation_id VARCHAR(255),
    duration_ms INTEGER NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    resource_usage JSONB DEFAULT '{}',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance monitoring
CREATE INDEX IF NOT EXISTS idx_performance_monitoring_operation 
ON performance_monitoring (operation_type, timestamp DESC);

-- Create function to update scaling metrics
CREATE OR REPLACE FUNCTION update_scaling_metrics()
RETURNS VOID AS $$
BEGIN
    INSERT INTO system_scaling_metrics (
        total_articles,
        raw_articles,
        processing_articles,
        completed_articles,
        failed_articles,
        total_timeline_events,
        active_storylines,
        database_size_bytes
    )
    SELECT 
        (SELECT COUNT(*) FROM articles),
        (SELECT COUNT(*) FROM articles WHERE processing_status = 'raw'),
        (SELECT COUNT(*) FROM articles WHERE processing_status = 'ml_processing'),
        (SELECT COUNT(*) FROM articles WHERE processing_status = 'completed'),
        (SELECT COUNT(*) FROM articles WHERE processing_status = 'failed'),
        (SELECT COUNT(*) FROM timeline_events),
        (SELECT COUNT(*) FROM story_expectations WHERE is_active = true),
        pg_database_size('news_system');
END;
$$ LANGUAGE plpgsql;

-- Create function for cleanup operations
CREATE OR REPLACE FUNCTION run_cleanup_policies()
RETURNS TABLE(policy_name TEXT, cleaned_count INTEGER) AS $$
DECLARE
    policy RECORD;
    cleaned_count INTEGER;
BEGIN
    FOR policy IN 
        SELECT * FROM storage_cleanup_policies WHERE is_active = true
    LOOP
        EXECUTE format('DELETE FROM %I WHERE %s', policy.table_name, policy.cleanup_condition);
        GET DIAGNOSTICS cleaned_count = ROW_COUNT;
        
        UPDATE storage_cleanup_policies 
        SET last_run = CURRENT_TIMESTAMP, last_cleaned_count = cleaned_count
        WHERE id = policy.id;
        
        policy_name := policy.policy_name;
        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create function to check rate limits
CREATE OR REPLACE FUNCTION check_rate_limit(
    p_resource_type VARCHAR(50),
    p_resource_key VARCHAR(255),
    p_max_requests INTEGER,
    p_window_duration_seconds INTEGER
)
RETURNS BOOLEAN AS $$
DECLARE
    current_count INTEGER;
    window_start TIMESTAMP;
BEGIN
    window_start := CURRENT_TIMESTAMP - INTERVAL '1 second' * p_window_duration_seconds;
    
    SELECT COALESCE(SUM(request_count), 0)
    INTO current_count
    FROM rate_limiting
    WHERE resource_type = p_resource_type 
      AND resource_key = p_resource_key
      AND window_start >= window_start;
    
    IF current_count >= p_max_requests THEN
        RETURN FALSE;
    END IF;
    
    -- Record this request
    INSERT INTO rate_limiting (resource_type, resource_key, max_requests, window_duration_seconds)
    VALUES (p_resource_type, p_resource_key, p_max_requests, p_window_duration_seconds)
    ON CONFLICT (resource_type, resource_key, window_start) 
    DO UPDATE SET request_count = rate_limiting.request_count + 1;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
