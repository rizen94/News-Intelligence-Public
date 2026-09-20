-- Migration 299: Unified discovery findings queue → editorial research filter.

CREATE TABLE IF NOT EXISTS intelligence.connection_findings (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finding_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    domain_keys TEXT[] NOT NULL DEFAULT '{}',
    confidence REAL,
    title TEXT,
    summary TEXT,
    left_kind TEXT,
    left_id BIGINT,
    right_kind TEXT,
    right_id BIGINT,
    source_table TEXT,
    source_id TEXT,
    dedupe_key TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    editorial_package_id BIGINT REFERENCES intelligence.editorial_packages (id) ON DELETE SET NULL,
    research_decision TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT connection_findings_status_check CHECK (
        status IN (
            'open',
            'queued_research',
            'researching',
            'linked',
            'dismissed',
            'superseded'
        )
    ),
    CONSTRAINT uq_connection_findings_dedupe UNIQUE (dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_connection_findings_status_created
    ON intelligence.connection_findings (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_connection_findings_package
    ON intelligence.connection_findings (editorial_package_id)
    WHERE editorial_package_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_connection_findings_type_open
    ON intelligence.connection_findings (finding_type)
    WHERE status IN ('open', 'queued_research', 'researching');

COMMENT ON TABLE intelligence.connection_findings IS
    'Discovery queue: concurrent/cross-domain/graph/pattern leads before editorial research filters them.';

DO $$
BEGIN
    RAISE NOTICE 'Migration 299: intelligence.connection_findings created';
END $$;
