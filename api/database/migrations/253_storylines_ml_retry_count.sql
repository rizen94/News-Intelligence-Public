-- =============================================================================
-- 253_storylines_ml_retry_count: Track ML processing retry attempts on storylines
-- =============================================================================
-- Purpose: Prevent infinite retry loops for comprehensive_rag jobs when the LLM
-- service fails (Ollama pressure, network issues, etc.). Without this counter,
-- failed items get re-queued immediately by the queue monitor because no
-- terminal status or retry limit was enforced.
--
-- The queue service selects storylines where ml_processing_status IN ('pending',
-- 'raw'), sets them to 'ml_processing', and enqueues RAG jobs. When the LLM
-- call fails, the job resets to 'pending' — causing immediate re-pickup on the
-- next queue cycle if no retry counter exists.
--
-- This migration adds ml_retry_count to all domain storylines tables (politics,
-- finance, science_tech, health) so that after MAX_RETRY_COUNT (default 3)
-- failures, the status transitions permanently to 'failed'.

DO $$
DECLARE
    s text;
    rec record;
BEGIN
    FOR rec IN SELECT table_schema FROM information_schema.tables
               WHERE table_name = 'storylines' AND table_type = 'BASE TABLE'
                 AND table_schema NOT IN ('pg_catalog', 'information_schema')
    LOOP
        s := format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS ml_retry_count INTEGER DEFAULT 0',
            rec.table_schema
        );
        EXECUTE s;

        -- Backfill: existing pending items that likely already failed once or more
        -- get count=1 so they don't silently cycle if the column was previously absent.
        s := format(
            $u$UPDATE %I.storylines SET ml_retry_count = GREATEST(ml_retry_count, 1)
              WHERE ml_processing_status = 'pending' AND ml_processing_error IS NOT NULL$u$,
            rec.table_schema
        );
        EXECUTE s;
    END LOOP;
END $$;
