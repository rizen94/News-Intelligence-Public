-- Reader/vault reconciliation: map retired storyline ids → canonical episode ids.
-- See docs/NARRATIVE_ASSEMBLY_SOURCE_STAGES.md §6.C

BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.storyline_id_lineage (
    id BIGSERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    old_storyline_id BIGINT NOT NULL,
    canonical_storyline_id BIGINT NOT NULL,
    reason TEXT NOT NULL DEFAULT 'merged',
    merged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_storyline_id_lineage_domain_old UNIQUE (domain_key, old_storyline_id)
);

CREATE INDEX IF NOT EXISTS idx_storyline_id_lineage_canonical
    ON intelligence.storyline_id_lineage (domain_key, canonical_storyline_id);

COMMENT ON TABLE intelligence.storyline_id_lineage IS
    'Projection: old storyline_id → canonical active episode id for reader hrefs and vault gates.';

COMMIT;