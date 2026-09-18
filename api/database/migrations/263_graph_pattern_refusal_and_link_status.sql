-- Migration 263: Pattern refuse ledger + soft status on graph_connection_links.
-- Enables break/reconnect quality loop: refuse/quarantine pairs, unlink without losing history.

CREATE TABLE IF NOT EXISTS intelligence.graph_pattern_refusals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint_key TEXT NOT NULL,
    dedupe_key TEXT,
    status TEXT NOT NULL DEFAULT 'refuse'
        CHECK (status IN ('refuse', 'quarantine', 'supersede', 'reopened')),
    reason TEXT,
    domain_key TEXT,
    endpoints JSONB,
    source TEXT NOT NULL DEFAULT 'operator',
    proposal_id BIGINT REFERENCES intelligence.graph_connection_proposals (id) ON DELETE SET NULL,
    vault_path TEXT
);

COMMENT ON TABLE intelligence.graph_pattern_refusals IS
    'Pattern refuse ledger: endpoint pairs that must not be auto-proposed until reopened. '
    'endpoint_key is source-agnostic (e.g. entity|politics|12|34) so different dedupe_keys hit the same refuse.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_pattern_refusals_endpoint_key
    ON intelligence.graph_pattern_refusals (endpoint_key);

CREATE INDEX IF NOT EXISTS idx_graph_pattern_refusals_active
    ON intelligence.graph_pattern_refusals (status, updated_at DESC)
    WHERE status IN ('refuse', 'quarantine', 'supersede');

ALTER TABLE intelligence.graph_connection_links
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'graph_connection_links_status_check'
    ) THEN
        ALTER TABLE intelligence.graph_connection_links
            ADD CONSTRAINT graph_connection_links_status_check
            CHECK (status IN ('active', 'broken', 'quarantined'));
    END IF;
END $$;

COMMENT ON COLUMN intelligence.graph_connection_links.status IS
    'active = live edge; broken = torn down (mistake); quarantined = isolated for learning.';

CREATE INDEX IF NOT EXISTS idx_graph_connection_links_active
    ON intelligence.graph_connection_links (left_kind, left_id)
    WHERE status = 'active';

DO $$
BEGIN
    RAISE NOTICE 'Migration 263: graph_pattern_refusals + graph_connection_links.status';
END $$;
