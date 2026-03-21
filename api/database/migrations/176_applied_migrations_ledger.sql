-- Migration 176: Applied migrations ledger (operational record of what ran where)
-- Reduces drift when SQL files exist but a database never executed them.
-- Populate via api/scripts/register_applied_migration.py or INSERT after manual runs.

CREATE TABLE IF NOT EXISTS public.applied_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checksum TEXT,
    environment TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_applied_migrations_applied_at ON public.applied_migrations (applied_at DESC);

COMMENT ON TABLE public.applied_migrations IS 'Human- or script-recorded migration applications; not auto-run by the API.';

DO $$
BEGIN
    GRANT SELECT, INSERT, UPDATE, DELETE ON public.applied_migrations TO newsapp;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Grant applied_migrations skipped: %', SQLERRM;
END $$;
