-- Migration 270: graph link provenance for self-reviewing graph
-- Survives proposal resolve/delete; supports drift re-score timestamps.

ALTER TABLE intelligence.graph_connection_links
    ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE intelligence.graph_connection_links
    ADD COLUMN IF NOT EXISTS last_scored_at TIMESTAMPTZ;

ALTER TABLE intelligence.graph_connection_links
    ADD COLUMN IF NOT EXISTS source TEXT;

COMMENT ON COLUMN intelligence.graph_connection_links.evidence IS
    'Auditable score/provenance snapshot: phase, method, score_parts, anchors, refusal_key';
COMMENT ON COLUMN intelligence.graph_connection_links.source IS
    'Writer phase (e.g. embedding_link_ranker, link_indexer_cross_domain, graph_connection_distillation)';
COMMENT ON COLUMN intelligence.graph_connection_links.last_scored_at IS
    'Last embedding/structural re-score time for drift review';

CREATE INDEX IF NOT EXISTS idx_graph_connection_links_drift
    ON intelligence.graph_connection_links (status, last_scored_at NULLS FIRST, confidence)
    WHERE status = 'active';
