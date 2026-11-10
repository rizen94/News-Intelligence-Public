-- Migration 237_cleanup_pipeline_schema.sql
-- Final cleanup of duplicate pipeline tables and proper schema consolidation
-- Created: 2026-11-10

-- Drop all duplicate tables from infrastructure schema that exist in pipeline schema
DROP TABLE IF EXISTS infrastructure.pipeline_alerts;
DROP TABLE IF EXISTS infrastructure.pipeline_checkpoints;
DROP TABLE IF EXISTS infrastructure.pipeline_traces;

-- Drop all duplicate tables from public schema that exist in pipeline schema
DROP TABLE IF EXISTS public.pipeline_alerts;
DROP TABLE IF EXISTS public.pipeline_checkpoints;
DROP TABLE IF EXISTS public.pipeline_traces;
DROP TABLE IF EXISTS public.pipeline_automation_status;
DROP TABLE IF EXISTS public.pipeline_error_log;
DROP TABLE IF EXISTS public.pipeline_performance_metrics;

-- Ensure pipeline schema tables are properly maintained and have correct data
-- The pipeline schema should contain all the monitoring and tracking data

COMMENT ON SCHEMA pipeline IS 'Pipeline tracking tables for RSS feeds, articles, and storylines';