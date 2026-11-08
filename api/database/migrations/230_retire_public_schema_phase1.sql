-- Phase 1: Create infrastructure schema and migrate automation/monitoring tables
-- This is the foundation for retiring the public schema

BEGIN;

-- Create infrastructure schema if not exists
CREATE SCHEMA IF NOT EXISTS infrastructure;
GRANT ALL ON SCHEMA infrastructure TO newsapp;

-- Migrate automation_run_history (250 MB) to infrastructure
CREATE TABLE IF NOT EXISTS infrastructure.automation_run_history (
    LIKE public.automation_run_history INCLUDING ALL
);
INSERT INTO infrastructure.automation_run_history SELECT * FROM public.automation_run_history;
DROP TABLE public.automation_run_history;

-- Migrate automation_state
CREATE TABLE IF NOT EXISTS infrastructure.automation_state (
    LIKE public.automation_state INCLUDING ALL
);
INSERT INTO infrastructure.automation_state SELECT * FROM public.automation_state;
DROP TABLE public.automation_state;

-- Migrate automation_tasks
CREATE TABLE IF NOT EXISTS infrastructure.automation_tasks (
    LIKE public.automation_tasks INCLUDING ALL
);
INSERT INTO infrastructure.automation_tasks SELECT * FROM public.automation_tasks;
DROP TABLE public.automation_tasks;

-- Migrate automation_logs
CREATE TABLE IF NOT EXISTS infrastructure.automation_logs (
    LIKE public.automation_logs INCLUDING ALL
);
INSERT INTO infrastructure.automation_logs SELECT * FROM public.automation_logs;
DROP TABLE public.automation_logs;

COMMIT;
