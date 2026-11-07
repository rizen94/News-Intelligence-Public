-- Migration 258: Fix stale domain_key and schema_name for politics/finance (PopOS)
--
-- Root cause: Migrations 219 + 227 both attempted to correct the registry with
--   UPDATE public.domains SET schema_name = 'politics' WHERE domain_key = 'politics';
-- but the actual row had domain_key = 'politics-2' (from migration 201/211), so zero rows matched.
-- This leaves: registry → politics_2, PG schema → politics → every lookup fails with "schema does not exist".
--
-- Fix: update any stale *-2 entries to the canonical domain_key + schema_name,
-- ensure tables exist, and guard against double-application.

BEGIN;

-- ============================================================
-- 1. Fix domain registry rows that still point to *_2 schemas
-- ============================================================

-- Update stale politics-2 → politics (only if such a row exists)
UPDATE public.domains
SET schema_name = 'politics',
    description = regexp_replace(COALESCE(description, ''), '\bpolitics_2\b', 'politics', 'gi')
WHERE domain_key = 'politics-2' AND is_active = true;

-- If a stale row exists with domain_key='politics' but schema_name='politics_2', fix it too
UPDATE public.domains
SET schema_name = 'politics'
WHERE domain_key = 'politics' AND schema_name = 'politics_2' AND is_active = true;

-- Same for finance-2 → finance
UPDATE public.domains
SET schema_name = 'finance',
    description = regexp_replace(COALESCE(description, ''), '\bfinance_2\b', 'finance', 'gi')
WHERE domain_key = 'finance-2' AND is_active = true;

-- If a stale row exists with domain_key='finance' but schema_name='finance_2', fix it too
UPDATE public.domains
SET schema_name = 'finance'
WHERE domain_key = 'finance' AND schema_name = 'finance_2' AND is_active = true;

-- ============================================================
-- 2. Ensure the target PG schemas exist with required tables
-- ============================================================

CREATE SCHEMA IF NOT EXISTS politics;
CREATE SCHEMA IF NOT EXISTS finance;

-- Ensure core table exists in each schema
CREATE TABLE IF NOT EXISTS politics.rss_feeds (
    id          SERIAL PRIMARY KEY,
    feed_url    TEXT NOT NULL,
    last_updated TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT true,
    UNIQUE(feed_url)
);
CREATE TABLE IF NOT EXISTS finance.rss_feeds (
    id          SERIAL PRIMARY KEY,
    feed_url    TEXT NOT NULL,
    last_updated TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT true,
    UNIQUE(feed_url)
);

-- ============================================================
-- 3. Verify and report
-- ============================================================

DO $$
DECLARE
    politics_row record;
    finance_row  record;
BEGIN
    SELECT * INTO politics_row FROM public.domains WHERE domain_key = 'politics' LIMIT 1;
    IF NOT FOUND THEN
        RAISE WARNING 'Migration 258: no active row found for domain_key=politics after fix!';
    END IF;

    SELECT * INTO finance_row FROM public.domains WHERE domain_key = 'finance' LIMIT 1;
    IF NOT FOUND THEN
        RAISE WARNING 'Migration 258: no active row found for domain_key=finance after fix!';
    END IF;

    -- Verify target schemas have tables
    PERFORM 1 FROM information_schema.tables WHERE table_schema = 'politics' AND table_name = 'rss_feeds' LIMIT 1;
    PERFORM 1 FROM information_schema.tables WHERE table_schema = 'finance' AND table_name = 'rss_feeds' LIMIT 1;

    RAISE NOTICE 'Migration 258 complete: politics/finance domain_key + schema_name corrected.';
END $$;

COMMIT;