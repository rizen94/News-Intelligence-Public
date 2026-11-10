-- Migration 241_cleanup_pipeline_phase_heartbeats.sql
-- Clean up pipeline phase heartbeats table structure and ensure consistency

-- Drop any incorrect tables from infrastructure and public schemas if they exist
DROP TABLE IF EXISTS infrastructure.pipeline_phase_heartbeats;
DROP TABLE IF EXISTS public.pipeline_phase_heartbeats;

-- Ensure the pipeline schema table exists with correct structure
CREATE TABLE IF NOT EXISTS pipeline.pipeline_phase_heartbeats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phase_name VARCHAR(255) NOT NULL,
    last_heartbeat TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    status VARCHAR(100) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_pipeline_phase_heartbeats_last_heartbeat ON pipeline.pipeline_phase_heartbeats(last_heartbeat);
CREATE INDEX IF NOT EXISTS idx_pipeline_phase_heartbeats_phase_name ON pipeline.pipeline_phase_heartbeats(phase_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_phase_heartbeats_status ON pipeline.pipeline_phase_heartbeats(status);

COMMENT ON TABLE pipeline.pipeline_phase_heartbeats IS 'Tracks heartbeats for pipeline phases';