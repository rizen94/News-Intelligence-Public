-- Migration 238: On-demand article "Pull context" executive summaries
-- Stores job status + markdown result assembled from vault + RAG + DB.

CREATE SCHEMA IF NOT EXISTS intelligence;

CREATE TABLE IF NOT EXISTS intelligence.article_context_pulls (
    id BIGSERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    article_id INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'ready', 'failed')),
    summary_markdown TEXT,
    error_message TEXT,
    context_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_tag TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_article_context_pulls_article
    ON intelligence.article_context_pulls (domain_key, article_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_article_context_pulls_status
    ON intelligence.article_context_pulls (status)
    WHERE status IN ('pending', 'running');

COMMENT ON TABLE intelligence.article_context_pulls IS
    'On-demand executive summaries: vault pack + storyline RAG + article text → LLM.';
