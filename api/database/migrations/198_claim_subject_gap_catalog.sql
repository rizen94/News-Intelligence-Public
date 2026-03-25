-- Unpromoted high-confidence claim subjects that still lack entity_profiles / domain canonical coverage.
-- Operators refresh snapshots via API or script; seed rows into {domain}.entity_canonical then run entity_profile_sync.

CREATE TABLE IF NOT EXISTS intelligence.claim_subject_gap_catalog (
    id BIGSERIAL PRIMARY KEY,
    subject_norm TEXT NOT NULL,
    sample_subject TEXT NOT NULL,
    domain_key VARCHAR(64) NOT NULL,
    unpromoted_claim_count INTEGER NOT NULL DEFAULT 0,
    last_refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(24) NOT NULL DEFAULT 'open',
    notes TEXT,
    CONSTRAINT claim_subject_gap_status_chk CHECK (status IN ('open', 'seeded', 'ignored'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_claim_subject_gap_norm_domain
    ON intelligence.claim_subject_gap_catalog (subject_norm, domain_key);

CREATE INDEX IF NOT EXISTS idx_claim_subject_gap_refreshed
    ON intelligence.claim_subject_gap_catalog (last_refreshed_at DESC);

CREATE INDEX IF NOT EXISTS idx_claim_subject_gap_status_count
    ON intelligence.claim_subject_gap_catalog (status, unpromoted_claim_count DESC);

COMMENT ON TABLE intelligence.claim_subject_gap_catalog IS
    'Research list: unpromoted claim subject strings (per domain) lacking profile/canonical; refresh replaces stale open rows.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.claim_subject_gap_catalog TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.claim_subject_gap_catalog_id_seq TO newsapp;
