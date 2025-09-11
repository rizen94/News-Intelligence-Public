-- ML Processing Timing Schema Updates
-- Add timing tracking for ML operations and background processing

-- Add ML timing columns to articles table if they don't exist
DO $$ 
BEGIN
    -- Add ML processing timing columns
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_processing_started_at'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_processing_started_at TIMESTAMP;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_processing_completed_at'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_processing_completed_at TIMESTAMP;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_processing_duration_seconds'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_processing_duration_seconds DECIMAL(8,3);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_processing_status'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_processing_status VARCHAR(50) DEFAULT 'pending';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_processing_error'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_processing_error TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_model_used'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_model_used VARCHAR(100);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_processing_metadata'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_processing_metadata JSONB DEFAULT '{}';
    END IF;
END $$;

-- Create ML processing logs table for detailed timing tracking
CREATE TABLE IF NOT EXISTS ml_processing_logs (
    log_id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    
    -- Processing details
    operation_type VARCHAR(50) NOT NULL, -- 'summarization', 'key_points', 'argument_analysis', 'sentiment'
    model_name VARCHAR(100) NOT NULL,
    
    -- Timing information
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds DECIMAL(8,3),
    
    -- Processing results
    status VARCHAR(50) NOT NULL, -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    
    -- Content metrics
    input_length INTEGER,
    output_length INTEGER,
    
    -- Performance metrics
    tokens_generated INTEGER,
    tokens_per_second DECIMAL(8,2),
    
    -- Additional metadata
    processing_metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create ML processing queue table for background tasks
CREATE TABLE IF NOT EXISTS ml_processing_queue (
    queue_id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    
    -- Queue management
    priority INTEGER DEFAULT 0, -- Higher number = higher priority
    status VARCHAR(50) DEFAULT 'queued', -- 'queued', 'processing', 'completed', 'failed', 'cancelled'
    
    -- Processing details
    operation_type VARCHAR(50) NOT NULL, -- 'summarization', 'key_points', 'argument_analysis', 'sentiment', 'full_analysis'
    model_name VARCHAR(100) NOT NULL,
    
    -- Timing
    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Results
    result_data JSONB,
    error_message TEXT,
    
    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Additional metadata
    processing_metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_articles_ml_processing_status ON articles(ml_processing_status);
CREATE INDEX IF NOT EXISTS idx_articles_ml_processing_started_at ON articles(ml_processing_started_at);
CREATE INDEX IF NOT EXISTS idx_articles_ml_processing_completed_at ON articles(ml_processing_completed_at);

CREATE INDEX IF NOT EXISTS idx_ml_processing_logs_article_id ON ml_processing_logs(article_id);
CREATE INDEX IF NOT EXISTS idx_ml_processing_logs_operation_type ON ml_processing_logs(operation_type);
CREATE INDEX IF NOT EXISTS idx_ml_processing_logs_status ON ml_processing_logs(status);
CREATE INDEX IF NOT EXISTS idx_ml_processing_logs_started_at ON ml_processing_logs(started_at);

CREATE INDEX IF NOT EXISTS idx_ml_processing_queue_status ON ml_processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_ml_processing_queue_priority ON ml_processing_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_ml_processing_queue_queued_at ON ml_processing_queue(queued_at);
CREATE INDEX IF NOT EXISTS idx_ml_processing_queue_article_id ON ml_processing_queue(article_id);

-- Create a view for ML processing statistics
CREATE OR REPLACE VIEW ml_processing_stats AS
SELECT 
    DATE(ml_processing_started_at) as processing_date,
    ml_model_used,
    COUNT(*) as total_processed,
    AVG(ml_processing_duration_seconds) as avg_duration_seconds,
    MIN(ml_processing_duration_seconds) as min_duration_seconds,
    MAX(ml_processing_duration_seconds) as max_duration_seconds,
    COUNT(CASE WHEN ml_processing_status = 'completed' THEN 1 END) as successful_count,
    COUNT(CASE WHEN ml_processing_status = 'failed' THEN 1 END) as failed_count
FROM articles 
WHERE ml_processing_started_at IS NOT NULL
GROUP BY DATE(ml_processing_started_at), ml_model_used
ORDER BY processing_date DESC, ml_model_used;

-- Create a view for queue status
CREATE OR REPLACE VIEW ml_queue_status AS
SELECT 
    status,
    operation_type,
    model_name,
    COUNT(*) as queue_count,
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - queued_at))) as avg_wait_time_seconds,
    MIN(queued_at) as oldest_queued_item
FROM ml_processing_queue 
WHERE status IN ('queued', 'processing')
GROUP BY status, operation_type, model_name
ORDER BY status, operation_type, model_name;
