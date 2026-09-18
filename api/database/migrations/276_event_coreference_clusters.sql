-- Migration 276: Event coreference clusters (narrative Phase 1)
-- Soft/hard links between chronological_events describing the same real-world event.

ALTER TABLE public.chronological_events
    ADD COLUMN IF NOT EXISTS event_cluster_id BIGINT;

COMMENT ON COLUMN public.chronological_events.event_cluster_id IS
    'Coreference cluster root (canonical chronological_events.id). Soft-linked members may set this without canonical_event_id.';

CREATE INDEX IF NOT EXISTS idx_chronological_events_event_cluster_id
    ON public.chronological_events (event_cluster_id)
    WHERE event_cluster_id IS NOT NULL;

-- Leaf/canonical rows in a cluster (for timeline listing)
CREATE INDEX IF NOT EXISTS idx_chronological_events_cluster_leaf
    ON public.chronological_events (event_cluster_id)
    WHERE event_cluster_id IS NOT NULL AND canonical_event_id IS NULL;

CREATE TABLE IF NOT EXISTS intelligence.event_coreference_links (
    id BIGSERIAL PRIMARY KEY,
    member_event_id BIGINT NOT NULL,
    canonical_event_id BIGINT NOT NULL,
    match_tier TEXT NOT NULL DEFAULT 'hard',
    score REAL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_event_coreference_member UNIQUE (member_event_id),
    CONSTRAINT chk_event_coreference_tier CHECK (
        match_tier IN ('fingerprint', 'embedding', 'entity_temporal', 'soft', 'hard')
    )
);

CREATE INDEX IF NOT EXISTS idx_event_coreference_links_canonical
    ON intelligence.event_coreference_links (canonical_event_id);

CREATE INDEX IF NOT EXISTS idx_event_coreference_links_tier
    ON intelligence.event_coreference_links (match_tier);

COMMENT ON TABLE intelligence.event_coreference_links IS
    'Auditable event coreference: member → cluster root. Soft tier does not set chronological_events.canonical_event_id.';
