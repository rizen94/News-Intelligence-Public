-- Migration 235_move_phase_heartbeats_to_pipeline_schema.sql
-- Fix for pipeline_phase_heartbeats table schema issues
-- This migration cleans up duplicate tables and ensures proper schema usage

-- First, drop the tables from infrastructure and public schemas if they exist
DROP TABLE IF EXISTS infrastructure.pipeline_phase_heartbeats;
DROP TABLE IF EXISTS public.pipeline_phase_heartbeats;

-- Ensure the pipeline schema table exists (it should already be created by previous migrations)
-- The table should remain in the pipeline schema as that's where it's used by the codebase