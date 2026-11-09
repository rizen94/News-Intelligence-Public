-- Migration 020_drop_empty_pipeline_tables
-- Drop empty pipeline tables that are not being used by any automation processes
-- Created: 2026-10-28

-- Drop pipeline_error_log table (empty)
DROP TABLE IF EXISTS pipeline.pipeline_error_log;

-- Drop pipeline_performance_metrics table (empty)
DROP TABLE IF EXISTS pipeline.pipeline_performance_metrics;

-- Drop pipeline_automation_status table (empty) - this was the main issue
DROP TABLE IF EXISTS pipeline.pipeline_automation_status;

-- Note: pipeline_traces and pipeline_checkpoints are kept as they contain actual data
-- Note: pipeline_phase_heartbeats is kept as it may be used for monitoring

COMMENT ON SCHEMA pipeline IS 'Pipeline tracking tables for RSS feeds, articles, and storylines';