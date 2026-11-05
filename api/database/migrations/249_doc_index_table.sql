-- 249 | doc_index — embed all docs/*.md so they become searchable via the same pgvector pipeline
-- Creates: (1) vector(768) column if missing, (2) pgvector extension, (3) HNSW index

-- Ensure pgvector is available
CREATE EXTENSION IF NOT EXISTS vector;

-- Create table (idempotent)
CREATE TABLE IF NOT EXISTS public.doc_index (
    id          bigserial PRIMARY KEY,
    file_path   text    NOT NULL,        -- relative path under project root (e.g. docs/KNOWLEDGE_LOOP.md)
    title       text,                     -- extracted from first H1; NULL when no heading
    headings    text,                     -- all H1-H3 headings joined with " > " for prefix context
    chunk_text  text    NOT NULL,         -- the actual searchable content window (~200-400 words)
    line_start  integer NOT NULL DEFAULT 1,
    line_end    integer NOT NULL DEFAULT 1,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    embedding   vector(768),              -- nomic-embed-text / bge-large output (768-d)
    CONSTRAINT chk_chunk_text CHECK (char_length(chunk_text) > 0)
);

-- Unique so we can UPSERT cleanly on file+line range identity
CREATE UNIQUE INDEX IF NOT EXISTS uq_doc_index_file_lines
    ON public.doc_index (file_path, line_start);

-- HNSW index for cosine similarity search (same config as migration 248)
CREATE INDEX IF NOT EXISTS idx_doc_index_embedding_hnsw
    ON public.doc_index
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Trigram GIN index for fallback text search when embedding is NULL
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_doc_index_chunk_text_gin
    ON public.doc_index USING gin (chunk_text gin_trgm_ops);
