-- v5.0 Phase 2: pgvector extension and event embedding columns
-- Enables native vector similarity search for cross-source event deduplication.

CREATE EXTENSION IF NOT EXISTS vector;

-- Event embeddings for semantic dedup (nomic-embed-text produces 768-dim vectors)
ALTER TABLE chronological_events
ADD COLUMN IF NOT EXISTS embedding vector(768);

-- Article-level embeddings (replaces any existing text-based embedding column)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'articles' AND column_name = 'embedding' AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE articles ADD COLUMN IF NOT EXISTS embedding vector(768);
    END IF;
END $$;

-- HNSW index for fast approximate nearest-neighbour search on events
CREATE INDEX IF NOT EXISTS idx_chrono_events_embedding
ON chronological_events USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- HNSW index on article embeddings
CREATE INDEX IF NOT EXISTS idx_articles_embedding
ON articles USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
