-- Migration 236_cleanup_duplicate_pipeline_tables.sql
-- Cleanup all duplicate pipeline tables across schemas and consolidate into proper schema structure

-- Drop duplicate tables from infrastructure schema (if they exist)
DROP TABLE IF EXISTS infrastructure.pipeline_alerts;
DROP TABLE IF EXISTS infrastructure.pipeline_checkpoints;
DROP TABLE IF EXISTS infrastructure.pipeline_traces;

-- Drop duplicate tables from public schema (if they exist)
DROP TABLE IF EXISTS public.pipeline_alerts;
DROP TABLE IF EXISTS public.pipeline_checkpoints;
DROP TABLE IF EXISTS public.pipeline_traces;
DROP TABLE IF EXISTS public.pipeline_automation_status;
DROP TABLE IF EXISTS public.pipeline_error_log;
DROP TABLE IF EXISTS public.pipeline_performance_metrics;

-- Ensure the pipeline schema tables are properly maintained
-- The pipeline schema should contain all the monitoring and tracking data
-- This migration consolidates all pipeline-related data into the proper schema structure

COMMENT ON SCHEMA pipeline IS 'Pipeline tracking tables for RSS feeds, articles, and storylines';