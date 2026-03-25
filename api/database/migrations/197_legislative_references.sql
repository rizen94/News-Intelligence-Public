-- Migration 197: Official legislative anchors for politics/legal — Congress.gov bill snapshots
-- linked to domain articles when bill citations are detected (automation: legislative_references).

CREATE TABLE IF NOT EXISTS intelligence.legislative_article_scans (
    domain_key TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    bills_found INTEGER NOT NULL DEFAULT 0,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (domain_key, article_id)
);

CREATE INDEX IF NOT EXISTS idx_legislative_article_scans_scanned
    ON intelligence.legislative_article_scans (scanned_at DESC);

COMMENT ON TABLE intelligence.legislative_article_scans IS
    'One row per article after bill-citation scan (including zero bills) to avoid reprocessing.';

CREATE TABLE IF NOT EXISTS intelligence.legislative_references (
    id SERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    congress INTEGER NOT NULL,
    bill_type TEXT NOT NULL,
    bill_number INTEGER NOT NULL,
    bill_metadata JSONB,
    summaries JSONB,
    text_versions JSONB,
    fetch_status TEXT NOT NULL DEFAULT 'ok',
    fetch_error TEXT,
    fetched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_legislative_ref_article_bill UNIQUE (domain_key, article_id, congress, bill_type, bill_number)
);

CREATE INDEX IF NOT EXISTS idx_legislative_ref_domain_article
    ON intelligence.legislative_references (domain_key, article_id);

CREATE INDEX IF NOT EXISTS idx_legislative_ref_bill
    ON intelligence.legislative_references (congress, bill_type, bill_number);

CREATE INDEX IF NOT EXISTS idx_legislative_ref_updated
    ON intelligence.legislative_references (updated_at DESC);

COMMENT ON TABLE intelligence.legislative_references IS
    'Congress.gov bill metadata + CRS summaries + text version pointers for a cited bill in an article; '
    'compare with intelligence.extracted_claims for media-vs-statute analysis.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.legislative_article_scans TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.legislative_references TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.legislative_references_id_seq TO newsapp;
