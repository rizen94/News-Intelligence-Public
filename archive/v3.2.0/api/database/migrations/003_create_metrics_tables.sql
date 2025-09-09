-- News Intelligence System v3.1.0 - Metrics Storage Schema
-- Long-term storage for system metrics and performance data

-- System metrics table for CPU, memory, disk usage
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    cpu_percent DECIMAL(5,2) NOT NULL,
    memory_percent DECIMAL(5,2) NOT NULL,
    memory_used_mb BIGINT NOT NULL,
    memory_total_mb BIGINT NOT NULL,
    disk_percent DECIMAL(5,2) NOT NULL,
    disk_used_gb DECIMAL(10,2) NOT NULL,
    disk_total_gb DECIMAL(10,2) NOT NULL,
    load_avg_1m DECIMAL(5,2),
    load_avg_5m DECIMAL(5,2),
    load_avg_15m DECIMAL(5,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Application metrics table for processing stats
CREATE TABLE IF NOT EXISTS application_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    articles_processed INTEGER DEFAULT 0,
    articles_failed INTEGER DEFAULT 0,
    processing_time_ms INTEGER DEFAULT 0,
    queue_size INTEGER DEFAULT 0,
    active_workers INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    avg_processing_time_ms DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Article volume metrics table
CREATE TABLE IF NOT EXISTS article_volume_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    total_articles INTEGER NOT NULL,
    new_articles_last_hour INTEGER DEFAULT 0,
    new_articles_last_day INTEGER DEFAULT 0,
    articles_by_source JSONB,
    articles_by_category JSONB,
    avg_article_length INTEGER DEFAULT 0,
    processing_success_rate DECIMAL(5,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Database performance metrics
CREATE TABLE IF NOT EXISTS database_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    connection_count INTEGER DEFAULT 0,
    active_queries INTEGER DEFAULT 0,
    slow_queries INTEGER DEFAULT 0,
    avg_query_time_ms DECIMAL(10,2) DEFAULT 0,
    database_size_mb DECIMAL(10,2) DEFAULT 0,
    table_sizes JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient time-based queries
CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_application_metrics_timestamp ON application_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_article_volume_metrics_timestamp ON article_volume_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_database_metrics_timestamp ON database_metrics(timestamp);

-- Create indexes for the last week queries (most common)
CREATE INDEX IF NOT EXISTS idx_system_metrics_last_week ON system_metrics(timestamp) 
    WHERE timestamp > NOW() - INTERVAL '7 days';
CREATE INDEX IF NOT EXISTS idx_application_metrics_last_week ON application_metrics(timestamp) 
    WHERE timestamp > NOW() - INTERVAL '7 days';
CREATE INDEX IF NOT EXISTS idx_article_volume_metrics_last_week ON article_volume_metrics(timestamp) 
    WHERE timestamp > NOW() - INTERVAL '7 days';
CREATE INDEX IF NOT EXISTS idx_database_metrics_last_week ON database_metrics(timestamp) 
    WHERE timestamp > NOW() - INTERVAL '7 days';

-- Create a view for easy last week data access
CREATE OR REPLACE VIEW metrics_last_week AS
SELECT 
    'system' as metric_type,
    timestamp,
    jsonb_build_object(
        'cpu_percent', cpu_percent,
        'memory_percent', memory_percent,
        'memory_used_mb', memory_used_mb,
        'memory_total_mb', memory_total_mb,
        'disk_percent', disk_percent,
        'load_avg_1m', load_avg_1m
    ) as data
FROM system_metrics 
WHERE timestamp > NOW() - INTERVAL '7 days'

UNION ALL

SELECT 
    'application' as metric_type,
    timestamp,
    jsonb_build_object(
        'articles_processed', articles_processed,
        'articles_failed', articles_failed,
        'processing_time_ms', processing_time_ms,
        'queue_size', queue_size,
        'active_workers', active_workers,
        'tasks_completed', tasks_completed,
        'avg_processing_time_ms', avg_processing_time_ms
    ) as data
FROM application_metrics 
WHERE timestamp > NOW() - INTERVAL '7 days'

UNION ALL

SELECT 
    'article_volume' as metric_type,
    timestamp,
    jsonb_build_object(
        'total_articles', total_articles,
        'new_articles_last_hour', new_articles_last_hour,
        'new_articles_last_day', new_articles_last_day,
        'articles_by_source', articles_by_source,
        'processing_success_rate', processing_success_rate
    ) as data
FROM article_volume_metrics 
WHERE timestamp > NOW() - INTERVAL '7 days'

UNION ALL

SELECT 
    'database' as metric_type,
    timestamp,
    jsonb_build_object(
        'connection_count', connection_count,
        'active_queries', active_queries,
        'avg_query_time_ms', avg_query_time_ms,
        'database_size_mb', database_size_mb
    ) as data
FROM database_metrics 
WHERE timestamp > NOW() - INTERVAL '7 days'

ORDER BY timestamp DESC;
