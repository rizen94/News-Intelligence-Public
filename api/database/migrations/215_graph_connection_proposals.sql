-- Migration 215: Queue for high-level graph connections (merge / associate / hyperedge).
-- Supports many-to-many style endpoints via JSONB; dedupe_key keeps one live row per logical edge/cluster.
-- Used by storyline consolidation first; entity/topic/cross-domain writers can reuse the same table.

CREATE TABLE IF NOT EXISTS intelligence.graph_connection_proposals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'auto_applied', 'applied_manual', 'rejected', 'superseded')),
    proposal_kind TEXT NOT NULL
        CHECK (proposal_kind IN ('merge', 'associate', 'hyperedge')),
    domain_key TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0::real AND confidence <= 1::real),
    min_confidence_for_auto REAL NOT NULL DEFAULT 0.72,
    source TEXT NOT NULL DEFAULT 'unknown',
    subject_summary TEXT,
    endpoints JSONB NOT NULL,
    evidence JSONB,
    dedupe_key TEXT NOT NULL,
    resolved_at TIMESTAMPTZ,
    resolution_note TEXT
);

COMMENT ON TABLE intelligence.graph_connection_proposals IS
    'Distillation queue: possible merges/links/hyperedges between storylines, topics, entities, events. '
    'endpoints JSONB holds typed id lists (e.g. storyline_ids, topic_ids, entity_ids). '
    'Many-to-many: one row can represent a cluster (hyperedge) or a pairwise merge; dedupe_key prevents spam.';

COMMENT ON COLUMN intelligence.graph_connection_proposals.proposal_kind IS
    'merge = collapse toward one canonical; associate = soft link without merge; hyperedge = multi-endpoint cluster.';

COMMENT ON COLUMN intelligence.graph_connection_proposals.min_confidence_for_auto IS
    'Policy hint for workers: auto-apply when confidence >= this (storyline consolidation still uses its own thresholds).';

CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_connection_proposals_dedupe_key
    ON intelligence.graph_connection_proposals (dedupe_key);

CREATE INDEX IF NOT EXISTS idx_graph_connection_proposals_pending_confidence
    ON intelligence.graph_connection_proposals (status, confidence DESC, created_at DESC)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_graph_connection_proposals_domain_kind
    ON intelligence.graph_connection_proposals (domain_key, proposal_kind, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_graph_connection_proposals_endpoints_gin
    ON intelligence.graph_connection_proposals USING gin (endpoints jsonb_path_ops);

DO $$
BEGIN
    RAISE NOTICE 'Migration 215: intelligence.graph_connection_proposals created';
END $$;
