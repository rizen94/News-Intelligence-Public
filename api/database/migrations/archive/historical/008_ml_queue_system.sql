-- ML Queue System Migration
-- Creates tables for managing ML task queue and resource monitoring

-- ML Task Queue Table
CREATE TABLE IF NOT EXISTS ml_task_queue (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) UNIQUE NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2,
    storyline_id VARCHAR(255),
    article_id INTEGER,
    payload JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSONB,
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    estimated_duration INTEGER DEFAULT 30,
    resource_requirements JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ml_task_queue_status ON ml_task_queue(status);
CREATE INDEX IF NOT EXISTS idx_ml_task_queue_priority ON ml_task_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_ml_task_queue_created_at ON ml_task_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_ml_task_queue_storyline_id ON ml_task_queue(storyline_id);
CREATE INDEX IF NOT EXISTS idx_ml_task_queue_article_id ON ml_task_queue(article_id);
CREATE INDEX IF NOT EXISTS idx_ml_task_queue_task_type ON ml_task_queue(task_type);

-- ML Resource Usage Table
CREATE TABLE IF NOT EXISTS ml_resource_usage (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cpu_usage DECIMAL(5,2),
    memory_usage DECIMAL(5,2),
    gpu_usage DECIMAL(5,2),
    active_tasks INTEGER DEFAULT 0,
    queue_size INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for resource usage queries
CREATE INDEX IF NOT EXISTS idx_ml_resource_usage_timestamp ON ml_resource_usage(timestamp);

-- ML Task Dependencies Table (for complex workflows)
CREATE TABLE IF NOT EXISTS ml_task_dependencies (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) NOT NULL,
    depends_on_task_id VARCHAR(255) NOT NULL,
    dependency_type VARCHAR(50) DEFAULT 'sequential',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES ml_task_queue(task_id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_task_id) REFERENCES ml_task_queue(task_id) ON DELETE CASCADE
);

-- Index for dependency queries
CREATE INDEX IF NOT EXISTS idx_ml_task_dependencies_task_id ON ml_task_dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_ml_task_dependencies_depends_on ON ml_task_dependencies(depends_on_task_id);

-- ML Performance Metrics Table
CREATE TABLE IF NOT EXISTS ml_performance_metrics (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    avg_duration DECIMAL(10,2),
    success_rate DECIMAL(5,2),
    total_tasks INTEGER DEFAULT 0,
    successful_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance metrics
CREATE INDEX IF NOT EXISTS idx_ml_performance_metrics_task_type ON ml_performance_metrics(task_type);

-- Update trigger for updated_at column
CREATE OR REPLACE FUNCTION update_ml_task_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_ml_task_queue_updated_at
    BEFORE UPDATE ON ml_task_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_ml_task_queue_updated_at();

-- Insert initial performance metrics
INSERT INTO ml_performance_metrics (task_type, avg_duration, success_rate, total_tasks, successful_tasks, failed_tasks)
VALUES 
    ('timeline_generation', 0.0, 0.0, 0, 0, 0),
    ('article_summarization', 0.0, 0.0, 0, 0, 0),
    ('content_analysis', 0.0, 0.0, 0, 0, 0),
    ('entity_extraction', 0.0, 0.0, 0, 0, 0),
    ('sentiment_analysis', 0.0, 0.0, 0, 0, 0),
    ('quality_scoring', 0.0, 0.0, 0, 0, 0),
    ('storyline_analysis', 0.0, 0.0, 0, 0, 0)
ON CONFLICT (task_type) DO NOTHING;
