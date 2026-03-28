-- Migration 207: Keep duplicate-source evidence without reprocessing duplicate articles.
-- Stores duplicate links to a canonical article so verification/reporting can use source_count
-- while heavy pipeline phases process the canonical row only.

CREATE TABLE IF NOT EXISTS intelligence.article_duplicate_sources (
    id BIGSERIAL PRIMARY KEY,
    domain_key VARCHAR(64) NOT NULL,
    schema_name VARCHAR(64) NOT NULL,
    canonical_article_id INTEGER NOT NULL,
    duplicate_url TEXT NOT NULL DEFAULT '',
    duplicate_source_domain VARCHAR(255) NOT NULL DEFAULT '',
    duplicate_title TEXT NOT NULL DEFAULT '',
    duplicate_published_at TIMESTAMPTZ,
    match_method VARCHAR(64) NOT NULL DEFAULT 'title_source',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    seen_count INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_article_dup_source_link
    ON intelligence.article_duplicate_sources (
        domain_key, canonical_article_id, duplicate_url, duplicate_source_domain, duplicate_title
    );

CREATE INDEX IF NOT EXISTS idx_article_dup_source_domain
    ON intelligence.article_duplicate_sources (domain_key, canonical_article_id);

COMMENT ON TABLE intelligence.article_duplicate_sources IS
    'Duplicate-source links to canonical per-domain articles; used for trust/verification reporting without reprocessing duplicate rows.';
