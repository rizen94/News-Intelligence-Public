-- Migration 255: Co-mention edge aggregation columns (v10.1)

BEGIN;

ALTER TABLE intelligence.entity_relationships
    ADD COLUMN IF NOT EXISTS co_occurrence_count INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN intelligence.entity_relationships.co_occurrence_count IS
    'Incremented on repeated co-mention upserts (link_indexer).';

COMMIT;
