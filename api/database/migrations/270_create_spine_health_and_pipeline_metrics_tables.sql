-- Migration 270: Create spine_health and pipeline_metrics tables
-- These tables will store health metrics and performance data for the news intelligence pipeline
-- This is part of the MVP materializer implementation for pipeline health monitoring

CREATE TABLE IF NOT EXISTS pipeline.spine_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    spine_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    health_score NUMERIC(5,2),
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline.pipeline_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(255) NOT NULL,
    value NUMERIC,
    unit VARCHAR(50),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(255),
    tags JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_spine_health_spine_name ON pipeline.spine_health (spine_name);
CREATE INDEX IF NOT EXISTS idx_spine_health_status ON pipeline.spine_health (status);
CREATE INDEX IF NOT EXISTS idx_spine_health_last_heartbeat ON pipeline.spine_health (last_heartbeat);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_metric_name ON pipeline.pipeline_metrics (metric_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_timestamp ON pipeline.pipeline_metrics (timestamp);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_source ON pipeline.pipeline_metrics (source);

-- Comments for documentation
COMMENT ON TABLE pipeline.spine_health IS 'Health status and metrics for pipeline spines';
COMMENT ON TABLE pipeline.pipeline_metrics IS 'Performance metrics and measurements for the news intelligence pipeline';

-- Migration completion notice
DO $$
BEGIN
    RAISE NOTICE 'Migration 270: spine_health and pipeline_metrics tables created successfully';
END $$;