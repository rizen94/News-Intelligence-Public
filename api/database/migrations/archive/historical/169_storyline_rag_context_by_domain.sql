-- Migration 169: v8 RAG — storyline context keyed by (domain_key, storyline_id)
-- Enables domain-aware RAG enhancement; no FK to domain storylines (they live in politics/finance/science_tech).

CREATE TABLE IF NOT EXISTS intelligence.storyline_rag_context (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    storyline_id INTEGER NOT NULL,
    rag_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain_key, storyline_id)
);

CREATE INDEX IF NOT EXISTS idx_storyline_rag_context_domain_storyline
ON intelligence.storyline_rag_context (domain_key, storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_rag_context_updated_at
ON intelligence.storyline_rag_context (updated_at DESC);

COMMENT ON TABLE intelligence.storyline_rag_context IS 'v8: RAG context per (domain_key, storyline_id). storyline_id refers to that domain schema (e.g. politics.storylines).';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.storyline_rag_context TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.storyline_rag_context_id_seq TO newsapp;
