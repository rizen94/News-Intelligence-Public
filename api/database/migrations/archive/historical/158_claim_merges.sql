-- Migration 158: Claim merges for P3 deduplication (merge_claims API)
CREATE TABLE IF NOT EXISTS intelligence.claim_merges (
    id SERIAL PRIMARY KEY,
    canonical_claim_id INTEGER NOT NULL,
    merged_claim_id INTEGER NOT NULL,
    merged_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(merged_claim_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_merges_canonical ON intelligence.claim_merges(canonical_claim_id);
COMMENT ON TABLE intelligence.claim_merges IS 'Tracks merged claims: merged_claim_id is represented by canonical_claim_id';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.claim_merges TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.claim_merges_id_seq TO newsapp;
