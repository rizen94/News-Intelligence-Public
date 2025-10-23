-- Migration 010: Search and ML Processing Tables
-- Creates tables for search functionality and ML processing management

-- Search Logs table for search analytics
CREATE TABLE IF NOT EXISTS search_logs (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    search_time FLOAT DEFAULT 0.0,
    user_id INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    filters JSONB DEFAULT '{}',
    search_type VARCHAR(20) DEFAULT 'full_text'
);

-- ML Processing Jobs table
CREATE TABLE IF NOT EXISTS ml_processing_jobs (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL DEFAULT 'full_processing',
    status VARCHAR(20) DEFAULT 'pending',
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    processing_time FLOAT,
    model_used VARCHAR(100),
    results JSONB DEFAULT '{}'
);

-- ML Model Performance table
CREATE TABLE IF NOT EXISTS ml_model_performance (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value FLOAT NOT NULL,
    measured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    context JSONB DEFAULT '{}'
);

-- Search Indexes for performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_search 
ON articles USING gin(to_tsvector('english', title || ' ' || content));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_title_search 
ON articles USING gin(to_tsvector('english', title));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_content_search 
ON articles USING gin(to_tsvector('english', content));

-- Search logs indexes
CREATE INDEX IF NOT EXISTS idx_search_logs_query ON search_logs(query);
CREATE INDEX IF NOT EXISTS idx_search_logs_timestamp ON search_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_search_logs_user_id ON search_logs(user_id);

-- ML processing jobs indexes
CREATE INDEX IF NOT EXISTS idx_ml_jobs_article_id ON ml_processing_jobs(article_id);
CREATE INDEX IF NOT EXISTS idx_ml_jobs_status ON ml_processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ml_jobs_created_at ON ml_processing_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_ml_jobs_priority ON ml_processing_jobs(priority);

-- ML model performance indexes
CREATE INDEX IF NOT EXISTS idx_ml_performance_model ON ml_model_performance(model_name);
CREATE INDEX IF NOT EXISTS idx_ml_performance_metric ON ml_model_performance(metric_name);
CREATE INDEX IF NOT EXISTS idx_ml_performance_measured_at ON ml_model_performance(measured_at);

-- Create triggers for updated_at timestamps
DROP TRIGGER IF EXISTS update_ml_jobs_updated_at ON ml_processing_jobs;
CREATE TRIGGER update_ml_jobs_updated_at
    BEFORE UPDATE ON ml_processing_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default ML model performance metrics
INSERT INTO ml_model_performance (model_name, model_version, metric_name, metric_value, context) VALUES
('summarization', '1.2.0', 'accuracy', 0.92, '{"dataset": "news_articles", "test_size": 1000}'),
('summarization', '1.2.0', 'rouge_l', 0.87, '{"dataset": "news_articles", "test_size": 1000}'),
('entity_extraction', '2.1.0', 'precision', 0.89, '{"dataset": "news_entities", "test_size": 500}'),
('entity_extraction', '2.1.0', 'recall', 0.91, '{"dataset": "news_entities", "test_size": 500}'),
('entity_extraction', '2.1.0', 'f1_score', 0.90, '{"dataset": "news_entities", "test_size": 500}'),
('sentiment_analysis', '1.5.0', 'accuracy', 0.87, '{"dataset": "news_sentiment", "test_size": 800}'),
('sentiment_analysis', '1.5.0', 'f1_score', 0.85, '{"dataset": "news_sentiment", "test_size": 800}'),
('clustering', '1.0.0', 'silhouette_score', 0.75, '{"dataset": "news_clusters", "clusters": 50}'),
('deduplication', '1.3.0', 'precision', 0.94, '{"dataset": "duplicate_pairs", "test_size": 300}'),
('deduplication', '1.3.0', 'recall', 0.91, '{"dataset": "duplicate_pairs", "test_size": 300}')
ON CONFLICT DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE search_logs IS 'Logs search queries and results for analytics and optimization';
COMMENT ON TABLE ml_processing_jobs IS 'Tracks ML processing jobs for articles';
COMMENT ON TABLE ml_model_performance IS 'Stores ML model performance metrics over time';

COMMENT ON COLUMN search_logs.search_time IS 'Search execution time in seconds';
COMMENT ON COLUMN search_logs.filters IS 'JSON object of search filters applied';
COMMENT ON COLUMN search_logs.search_type IS 'Type of search: full_text, semantic, hybrid';

COMMENT ON COLUMN ml_processing_jobs.job_type IS 'Type of processing: full_processing, summarization, entity_extraction, sentiment_analysis, clustering';
COMMENT ON COLUMN ml_processing_jobs.priority IS 'Processing priority (1-5, higher is more urgent)';
COMMENT ON COLUMN ml_processing_jobs.processing_time IS 'Total processing time in seconds';
COMMENT ON COLUMN ml_processing_jobs.results IS 'JSON object containing processing results';

COMMENT ON COLUMN ml_model_performance.metric_name IS 'Performance metric: accuracy, precision, recall, f1_score, latency, throughput, etc.';
COMMENT ON COLUMN ml_model_performance.metric_value IS 'Metric value (0.0-1.0 for accuracy metrics, seconds for latency, etc.)';
COMMENT ON COLUMN ml_model_performance.context IS 'JSON object with additional context about the measurement';
