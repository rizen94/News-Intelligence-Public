-- Migration 142: Context-centric foundation (Phase 1.1)
-- Adds contexts table and article_to_context mapping. No migration of existing data yet.
-- See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md

-- Ensure intelligence schema exists (from 141)
CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA intelligence GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO newsapp;

-- Universal content storage: one row per "content unit" (article, PDF section, etc.)
CREATE TABLE IF NOT EXISTS intelligence.contexts (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL DEFAULT 'article',  -- article, pdf_section, structured
    domain_key VARCHAR(50),                               -- domain of origin when source is article
    title TEXT,
    content TEXT,
    raw_content TEXT,                                      -- original before normalization
    language VARCHAR(10) DEFAULT 'en',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_contexts_source_type ON intelligence.contexts(source_type);
CREATE INDEX IF NOT EXISTS idx_intelligence_contexts_domain ON intelligence.contexts(domain_key);
CREATE INDEX IF NOT EXISTS idx_intelligence_contexts_created ON intelligence.contexts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intelligence_contexts_metadata ON intelligence.contexts USING GIN(metadata);

COMMENT ON TABLE intelligence.contexts IS 'Universal content units; articles and other sources map in via article_to_context or future link tables';

-- Links existing domain articles to contexts (one article -> one context for Phase 1)
-- No FK to articles: articles live in domain schemas (politics.articles, etc.)
CREATE TABLE IF NOT EXISTS intelligence.article_to_context (
    context_id INTEGER NOT NULL PRIMARY KEY REFERENCES intelligence.contexts(id) ON DELETE CASCADE,
    domain_key VARCHAR(50) NOT NULL,
    article_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain_key, article_id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_article_to_context_lookup ON intelligence.article_to_context(domain_key, article_id);

COMMENT ON TABLE intelligence.article_to_context IS 'Maps existing domain articles to contexts; preserves lineage for dual-mode and migration';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.contexts TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.article_to_context TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.contexts_id_seq TO newsapp;
