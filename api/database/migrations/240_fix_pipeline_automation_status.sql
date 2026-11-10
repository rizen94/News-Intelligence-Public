-- Migration 240_fix_pipeline_automation_status.sql
-- Fix for pipeline automation status table structure and schema placement
-- This migration ensures the pipeline_automation_status table is properly structured in the pipeline schema

-- First, drop the incorrect table from public schema if it exists (this was from a previous failed migration)
DROP TABLE IF EXISTS public.pipeline_automation_status;

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

COMMENT ON TABLE pipeline.pipeline_automation_status IS 'Tracks automation status for pipeline processes';