-- Migration 241_fix_pipeline_automation_status_comprehensive.sql
-- Comprehensive fix for pipeline automation status table schema and data issues

-- Drop all existing pipeline_automation_status tables from incorrect schemas
DROP TABLE IF EXISTS public.pipeline_automation_status;
DROP TABLE IF EXISTS infrastructure.pipeline_automation_status;
DROP TABLE IF EXISTS intelligence.pipeline_automation_status;

-- Create the correct pipeline_automation_status table in the pipeline schema
CREATE TABLE IF NOT EXISTS pipeline.pipeline_automation_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    automation_type VARCHAR(255) NOT NULL,
    status VARCHAR(100) NOT NULL,
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    total_processed INTEGER DEFAULT 0,
    current_trace_id VARCHAR(255),
    error_message TEXT,
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_pipeline_automation_status_last_run ON pipeline.pipeline_automation_status(last_run);
CREATE INDEX IF NOT EXISTS idx_pipeline_automation_status_status ON pipeline.pipeline_automation_status(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_automation_status_type ON pipeline.pipeline_automation_status(automation_type);

-- Add a check constraint to ensure status values are valid
ALTER TABLE pipeline.pipeline_automation_status 
ADD CONSTRAINT pipeline_automation_status_status_check 
CHECK (status IN ('idle', 'running', 'completed', 'failed', 'error', 'pending'));

-- Add comments for documentation
COMMENT ON TABLE pipeline.pipeline_automation_status IS 'Tracks automation status for pipeline processes';
COMMENT ON COLUMN pipeline.pipeline_automation_status.automation_type IS 'Type of automation process';
COMMENT ON COLUMN pipeline.pipeline_automation_status.status IS 'Current status of the automation';
COMMENT ON COLUMN pipeline.pipeline_automation_status.success_count IS 'Number of successful runs';
COMMENT ON COLUMN pipeline.pipeline_automation_status.error_count IS 'Number of failed runs';
COMMENT ON COLUMN pipeline.pipeline_automation_status.total_processed IS 'Total number of items processed';
COMMENT ON COLUMN pipeline.pipeline_automation_status.current_trace_id IS 'Current trace ID being processed';
COMMENT ON COLUMN pipeline.pipeline_automation_status.error_message IS 'Last error message if any';
COMMENT ON COLUMN pipeline.pipeline_automation_status.configuration IS 'Configuration settings for the automation';

-- Insert sample data to verify the table works correctly
INSERT INTO pipeline.pipeline_automation_status (
    automation_type, 
    status, 
    success_count, 
    error_count, 
    total_processed,
    configuration,
    created_at,
    updated_at
) VALUES 
(
    'rss_feed_processing',
    'idle',
    150,
    2,
    12500,
    '{"max_concurrent_feeds": 5, "timeout_seconds": 30}',
    NOW() - INTERVAL '1 day',
    NOW()
),
(
    'article_analysis',
    'running',
    89,
    1,
    7500,
    '{"max_concurrent_analyses": 3, "processing_timeout": 60}',
    NOW() - INTERVAL '2 hours',
    NOW()
),
(
    'storyline_generation',
    'completed',
    42,
    0,
    3200,
    '{"max_concurrent_generations": 2, "timeout_seconds": 120}',
    NOW() - INTERVAL '3 hours',
    NOW()
);

-- Verify the data was inserted
SELECT 
    automation_type,
    status,
    success_count,
    error_count,
    total_processed,
    created_at,
    updated_at
FROM pipeline.pipeline_automation_status 
ORDER BY updated_at DESC;