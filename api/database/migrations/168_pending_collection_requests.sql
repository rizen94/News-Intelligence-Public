-- Migration 168: Store for pending collection queue (v8 collect-then-analyze)
-- Persisted on shutdown, loaded on startup so RAG/synthesis-queued URLs survive restart.

CREATE TABLE IF NOT EXISTS public.automation_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE public.automation_state IS 'Key-value state for automation (e.g. pending_collection_queue); survives API restart';
