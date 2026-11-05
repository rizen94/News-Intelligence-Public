-- =============================================================================
-- 252_ml_processing_retry_count: Track ML processing retry attempts on articles
-- =============================================================================
-- Purpose: Prevent infinite retry loops when background_processor.py resets
-- articles to 'pending' after Ollama pressure errors. Without this counter,
-- failed items get re-queued immediately by daily_batch_processor and/or
-- the queue monitor, cycling indefinitely under sustained ML load.
--
-- The batch processor (daily_batch_processor.py) selects articles where
-- processing_status IN ('raw', 'pending', 'ml_processing'), sets them to
-- 'ml_processing', and enqueues them. When background_processor hits an
-- Ollama pressure error, it resets ml_processing_status = 'pending' AND
-- processing_status = 'pending' (via _update_article_processing_status),
-- causing immediate re-pickup on the next batch/queue cycle.
--
-- The retry counter provides a bounded retry window before permanent failure.

DO $$ BEGIN
    -- Add column only if it doesn't already exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'articles' AND column_name = 'ml_retry_count'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_retry_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- Backfill: existing articles that have been retried multiple times likely
-- already have ml_processing_error set. Mark them with count=1 so they don't
-- silently re-queue if the column was previously absent.
UPDATE articles SET ml_retry_count = GREATEST(ml_retry_count, 1)
WHERE ml_processing_status = 'pending' AND ml_processing_error IS NOT NULL;
