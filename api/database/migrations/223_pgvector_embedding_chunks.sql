-- Migration 223: pgvector extension + embedding_chunks for longitudinal retrieval
-- Phase 1 — requires pgvector on PostgreSQL host. See docs/LONGITUDINAL_INTELLIGENCE_EXECUTION.md

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS intelligence.embedding_chunks (
    id bigserial PRIMARY KEY,
    source_type text NOT NULL
        CHECK (source_type IN (
            'article', 'reference_event', 'wikipedia', 'context', 'arc_report'
        )),
    source_id text NOT NULL,
    domain_key text,
    chunk_index integer NOT NULL DEFAULT 0,
    chunk_text text NOT NULL,
    embedding vector(768),
    event_date timestamptz,
    ingestion_date timestamptz NOT NULL DEFAULT NOW(),
    vintage_date timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_embedding_chunks_source
    ON intelligence.embedding_chunks (source_type, source_id);

-- IVFFlat index — build after initial backfill on production; lists=100 is a starting point
CREATE INDEX IF NOT EXISTS idx_embedding_chunks_embedding_cosine
    ON intelligence.embedding_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

COMMENT ON TABLE intelligence.embedding_chunks IS
  'Chunked embeddings for slow-report retrieval (nomic-embed-text, 768 dims)';

COMMIT;
