-- Migration 191: Ensure public.ml_processing_queue exists (BackgroundMLProcessor + automation).
-- 190 only ALTERs when the table already exists; greenfield or partial DBs may lack the table.
-- Idempotent: CREATE IF NOT EXISTS + ADD COLUMN for schema_name if an old table lacked it.

CREATE TABLE IF NOT EXISTS public.ml_processing_queue (
    queue_id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL,
    operation_type VARCHAR(100) NOT NULL,
    model_name VARCHAR(255),
    priority INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    queued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result_data JSONB,
    error_message TEXT
);

ALTER TABLE public.ml_processing_queue
    ADD COLUMN IF NOT EXISTS schema_name VARCHAR(128);

COMMENT ON COLUMN public.ml_processing_queue.schema_name IS
    'Postgres silo schema (e.g. politics, science_tech). Set for new rows; legacy NULL rows resolved by scanning active schemas.';

CREATE INDEX IF NOT EXISTS idx_ml_processing_queue_queued
    ON public.ml_processing_queue (status, priority DESC, queued_at ASC)
    WHERE status = 'queued';

DO $$
BEGIN
    RAISE NOTICE 'Migration 191: public.ml_processing_queue ensured';
END $$;
