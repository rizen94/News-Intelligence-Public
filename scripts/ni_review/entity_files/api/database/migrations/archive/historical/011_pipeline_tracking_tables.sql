-- Migration 011: Pipeline Tracking Tables
-- Creates database schema for comprehensive pipeline tracking and logging
-- Created: 2025-01-09

-- Pipeline Traces Table
CREATE TABLE IF NOT EXISTS pipeline_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(100) NOT NULL UNIQUE,
    rss_feed_id VARCHAR(100),
    article_id VARCHAR(100),
    storyline_id VARCHAR(100),
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    total_duration_ms DECIMAL(10,2) DEFAULT 0.0,
    success BOOLEAN DEFAULT FALSE,
    error_stage VARCHAR(50),
    performance_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for pipeline_traces
CREATE INDEX IF NOT EXISTS idx_pipeline_traces_trace_id ON pipeline_traces(trace_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_traces_rss_feed_id ON pipeline_traces(rss_feed_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_traces_article_id ON pipeline_traces(article_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_traces_storyline_id ON pipeline_traces(storyline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_traces_start_time ON pipeline_traces(start_time);
CREATE INDEX IF NOT EXISTS idx_pipeline_traces_success ON pipeline_traces(success);
CREATE INDEX IF NOT EXISTS idx_pipeline_traces_error_stage ON pipeline_traces(error_stage);

-- Pipeline Checkpoints Table
CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checkpoint_id VARCHAR(100) NOT NULL UNIQUE,
    trace_id VARCHAR(100) NOT NULL,
    stage VARCHAR(50) NOT NULL,
    article_id VARCHAR(100),
    storyline_id VARCHAR(100),
    rss_feed_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_ms DECIMAL(10,2) DEFAULT 0.0,
    status VARCHAR(20) NOT NULL CHECK (status IN ('started', 'completed', 'failed', 'skipped')),
    input_data JSONB DEFAULT '{}'::jsonb,
    output_data JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for pipeline_checkpoints
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_checkpoint_id ON pipeline_checkpoints(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_trace_id ON pipeline_checkpoints(trace_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_stage ON pipeline_checkpoints(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_status ON pipeline_checkpoints(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_timestamp ON pipeline_checkpoints(timestamp);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_article_id ON pipeline_checkpoints(article_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_storyline_id ON pipeline_checkpoints(storyline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_rss_feed_id ON pipeline_checkpoints(rss_feed_id);

-- Pipeline Performance Metrics Table
CREATE TABLE IF NOT EXISTS pipeline_performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(20) NOT NULL,
    stage VARCHAR(50),
    trace_id VARCHAR(100),
    article_id VARCHAR(100),
    storyline_id VARCHAR(100),
    rss_feed_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for pipeline_performance_metrics
CREATE INDEX IF NOT EXISTS idx_pipeline_performance_metrics_name ON pipeline_performance_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_performance_metrics_stage ON pipeline_performance_metrics(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_performance_metrics_trace_id ON pipeline_performance_metrics(trace_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_performance_metrics_timestamp ON pipeline_performance_metrics(timestamp);

-- Pipeline Error Log Table
CREATE TABLE IF NOT EXISTS pipeline_error_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(100),
    checkpoint_id VARCHAR(100),
    stage VARCHAR(50) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    input_data JSONB DEFAULT '{}'::jsonb,
    context_data JSONB DEFAULT '{}'::jsonb,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    resolved BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for pipeline_error_log
CREATE INDEX IF NOT EXISTS idx_pipeline_error_log_trace_id ON pipeline_error_log(trace_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_error_log_checkpoint_id ON pipeline_error_log(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_error_log_stage ON pipeline_error_log(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_error_log_error_type ON pipeline_error_log(error_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_error_log_severity ON pipeline_error_log(severity);
CREATE INDEX IF NOT EXISTS idx_pipeline_error_log_resolved ON pipeline_error_log(resolved);
CREATE INDEX IF NOT EXISTS idx_pipeline_error_log_created_at ON pipeline_error_log(created_at);

-- Pipeline Automation Status Table
CREATE TABLE IF NOT EXISTS pipeline_automation_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    automation_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'paused', 'stopped', 'error')),
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    total_processed INTEGER DEFAULT 0,
    current_trace_id VARCHAR(100),
    error_message TEXT,
    configuration JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for pipeline_automation_status
CREATE INDEX IF NOT EXISTS idx_pipeline_automation_status_type ON pipeline_automation_status(automation_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_automation_status_status ON pipeline_automation_status(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_automation_status_last_run ON pipeline_automation_status(last_run);

-- Add foreign key constraints
DO $$
BEGIN
    -- Add foreign key for pipeline_checkpoints to pipeline_traces
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_pipeline_checkpoints_trace_id'
    ) THEN
        ALTER TABLE pipeline_checkpoints 
        ADD CONSTRAINT fk_pipeline_checkpoints_trace_id 
        FOREIGN KEY (trace_id) REFERENCES pipeline_traces(trace_id) ON DELETE CASCADE;
    END IF;
    
    -- Add foreign key for pipeline_performance_metrics to pipeline_traces
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_pipeline_performance_metrics_trace_id'
    ) THEN
        ALTER TABLE pipeline_performance_metrics 
        ADD CONSTRAINT fk_pipeline_performance_metrics_trace_id 
        FOREIGN KEY (trace_id) REFERENCES pipeline_traces(trace_id) ON DELETE CASCADE;
    END IF;
    
    -- Add foreign key for pipeline_error_log to pipeline_traces
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_pipeline_error_log_trace_id'
    ) THEN
        ALTER TABLE pipeline_error_log 
        ADD CONSTRAINT fk_pipeline_error_log_trace_id 
        FOREIGN KEY (trace_id) REFERENCES pipeline_traces(trace_id) ON DELETE CASCADE;
    END IF;
    
    -- Add foreign key for pipeline_error_log to pipeline_checkpoints
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_pipeline_error_log_checkpoint_id'
    ) THEN
        ALTER TABLE pipeline_error_log 
        ADD CONSTRAINT fk_pipeline_error_log_checkpoint_id 
        FOREIGN KEY (checkpoint_id) REFERENCES pipeline_checkpoints(checkpoint_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create update triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_pipeline_traces_updated_at 
    BEFORE UPDATE ON pipeline_traces 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pipeline_automation_status_updated_at 
    BEFORE UPDATE ON pipeline_automation_status 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default automation status records
INSERT INTO pipeline_automation_status (automation_type, status, configuration) VALUES
('rss_feed_processing', 'stopped', '{"enabled": false, "interval_minutes": 15, "batch_size": 10}'),
('article_processing', 'stopped', '{"enabled": false, "interval_minutes": 5, "batch_size": 20}'),
('storyline_analysis', 'stopped', '{"enabled": false, "interval_minutes": 30, "batch_size": 5}'),
('ml_processing', 'stopped', '{"enabled": false, "interval_minutes": 10, "batch_size": 15}'),
('comprehensive_analysis', 'stopped', '{"enabled": false, "interval_minutes": 60, "batch_size": 3}')
ON CONFLICT (automation_type) DO NOTHING;

-- Add table comments
COMMENT ON TABLE pipeline_traces IS 'Complete pipeline traces for RSS feeds, articles, and storylines';
COMMENT ON TABLE pipeline_checkpoints IS 'Individual checkpoints within pipeline traces';
COMMENT ON TABLE pipeline_performance_metrics IS 'Performance metrics for pipeline stages';
COMMENT ON TABLE pipeline_error_log IS 'Error log for pipeline failures and issues';
COMMENT ON TABLE pipeline_automation_status IS 'Status and configuration for automated pipeline processes';

-- Add column comments
COMMENT ON COLUMN pipeline_traces.trace_id IS 'Unique identifier for the pipeline trace';
COMMENT ON COLUMN pipeline_traces.total_duration_ms IS 'Total duration of the pipeline trace in milliseconds';
COMMENT ON COLUMN pipeline_traces.success IS 'Whether the pipeline trace completed successfully';
COMMENT ON COLUMN pipeline_traces.error_stage IS 'Stage where error occurred if trace failed';
COMMENT ON COLUMN pipeline_traces.performance_metrics IS 'JSON object containing performance metrics';

COMMENT ON COLUMN pipeline_checkpoints.stage IS 'Pipeline stage: rss_feed_discovery, article_extraction, ml_summarization, etc.';
COMMENT ON COLUMN pipeline_checkpoints.status IS 'Checkpoint status: started, completed, failed, skipped';
COMMENT ON COLUMN pipeline_checkpoints.duration_ms IS 'Duration of this checkpoint in milliseconds';
COMMENT ON COLUMN pipeline_checkpoints.input_data IS 'Input data for this checkpoint';
COMMENT ON COLUMN pipeline_checkpoints.output_data IS 'Output data from this checkpoint';
COMMENT ON COLUMN pipeline_checkpoints.metadata IS 'Additional metadata for this checkpoint';

COMMENT ON COLUMN pipeline_performance_metrics.metric_name IS 'Name of the performance metric';
COMMENT ON COLUMN pipeline_performance_metrics.metric_value IS 'Value of the performance metric';
COMMENT ON COLUMN pipeline_performance_metrics.metric_unit IS 'Unit of the metric (ms, tokens, records, etc.)';
COMMENT ON COLUMN pipeline_performance_metrics.stage IS 'Pipeline stage this metric relates to';

COMMENT ON COLUMN pipeline_error_log.error_type IS 'Type of error (connection, validation, processing, etc.)';
COMMENT ON COLUMN pipeline_error_log.severity IS 'Error severity: low, medium, high, critical';
COMMENT ON COLUMN pipeline_error_log.resolved IS 'Whether the error has been resolved';
COMMENT ON COLUMN pipeline_error_log.resolution_notes IS 'Notes on how the error was resolved';

COMMENT ON COLUMN pipeline_automation_status.automation_type IS 'Type of automation (rss_feed_processing, article_processing, etc.)';
COMMENT ON COLUMN pipeline_automation_status.status IS 'Current status of the automation';
COMMENT ON COLUMN pipeline_automation_status.success_count IS 'Number of successful runs';
COMMENT ON COLUMN pipeline_automation_status.error_count IS 'Number of failed runs';
COMMENT ON COLUMN pipeline_automation_status.total_processed IS 'Total number of items processed';
COMMENT ON COLUMN pipeline_automation_status.current_trace_id IS 'Current trace ID being processed';
