-- Migration 242_final_pipeline_cleanup.sql
-- Final cleanup for pipeline tables to ensure consistent structure

-- First, let's check what the correct structure should be based on our investigation
-- The pipeline_automation_status table was already fixed in migration 240

-- For pipeline_phase_heartbeats, we'll update it to have a more standard structure if needed
-- But since it already exists and is working, we'll just ensure consistency

-- Create a view for easier access to automation status data (if needed)
CREATE OR REPLACE VIEW pipeline.automation_status_summary AS
SELECT 
    automation_type,
    status,
    last_run,
    next_run,
    success_count,
    error_count,
    total_processed,
    created_at,
    updated_at
FROM pipeline.pipeline_automation_status;

-- Ensure all required tables exist with correct structure
-- The main issue was the structure of pipeline_automation_status which is now fixed

COMMENT ON VIEW pipeline.automation_status_summary IS 'Summary view for automation status tracking';