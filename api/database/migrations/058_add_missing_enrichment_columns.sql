-- Migration: Add enrichment_status and processing_status columns to articles table
-- Addresses: pipeline status inconsistency — fast-path enriched articles had
-- enrichment_status='enriched' but status=NULL, breaking downstream eligibility checks.
-- Columns were missing from the schema entirely (01_schema.sql).

BEGIN;

-- Add enrichment_status column if it doesn't exist yet
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'articles' AND column_name = 'enrichment_status'
    ) THEN
        ALTER TABLE articles ADD COLUMN enrichment_status varchar(50) DEFAULT NULL;
    END IF;
END $$;

-- Add processing_status column if it doesn't exist yet
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'articles' AND column_name = 'processing_status'
    ) THEN
        ALTER TABLE articles ADD COLUMN processing_status varchar(50) DEFAULT 'pending';
    END IF;
END $$;

-- Backfill: items enriched in code (enrichment_status='enriched') but with NULL status should be marked completed
UPDATE articles
SET status = 'completed'
WHERE enrichment_status = 'enriched'
  AND status IS NULL;

-- Also backfill any remaining pending items that were actually processed
-- (status='pending' but content is populated)
UPDATE articles
SET status = 'completed'
WHERE status = 'pending'
  AND content IS NOT NULL
  AND length(trim(content)) > 100
  AND status = 'pending';

COMMIT;
