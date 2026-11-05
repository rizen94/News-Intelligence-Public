-- 248 | pgvector HNSW index on chronological_events(embedding)
-- Creates: (1) vector(768) column if missing, (2) pgvector extension, (3) HNSW index

-- Ensure pgvector is available
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column if it does not exist (idempotent via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = 'chronological_events'
          AND c.column_name = 'embedding'
    ) THEN
        ALTER TABLE public.chronological_events
            ADD COLUMN embedding vector(768);
    END IF;
END $$;

-- Create the HNSW index if it does not already exist
CREATE INDEX CONCURRENTLY IF NOT EXISTS
    idx_chronological_events_embedding_hnsw
    ON public.chronological_events
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
