-- Migration 216: Applied high-level links (many-to-many) materialized from proposals.
-- Pairwise rows for hyperedges and soft associates; merge outcomes stay on domain tables + proposal status.

CREATE TABLE IF NOT EXISTS intelligence.graph_connection_links (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    domain_key TEXT,
    source_proposal_id BIGINT REFERENCES intelligence.graph_connection_proposals (id) ON DELETE SET NULL,
    left_kind TEXT NOT NULL,
    left_id BIGINT NOT NULL,
    right_kind TEXT NOT NULL,
    right_id BIGINT NOT NULL,
    link_role TEXT NOT NULL DEFAULT 'associated',
    confidence REAL,
    CONSTRAINT uq_graph_connection_link_endpoints UNIQUE (
        left_kind,
        left_id,
        right_kind,
        right_id,
        link_role
    )
);

COMMENT ON TABLE intelligence.graph_connection_links IS
    'Undirected logical edges between graph objects (storyline, topic, entity, tracked_event). '
    'Canonical pair order: (left_kind, left_id) lexicographically before (right_kind, right_id).';

CREATE INDEX IF NOT EXISTS idx_graph_connection_links_left
    ON intelligence.graph_connection_links (left_kind, left_id);

CREATE INDEX IF NOT EXISTS idx_graph_connection_links_right
    ON intelligence.graph_connection_links (right_kind, right_id);

CREATE INDEX IF NOT EXISTS idx_graph_connection_links_proposal
    ON intelligence.graph_connection_links (source_proposal_id);

DO $$
BEGIN
    RAISE NOTICE 'Migration 216: intelligence.graph_connection_links created';
END $$;
