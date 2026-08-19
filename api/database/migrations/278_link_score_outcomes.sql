-- Migration 278: Link-score training / calibration outcomes (Narrative Phase 3)
-- Desk / editorial / membership decisions on scored proposals for eval harness.

CREATE TABLE IF NOT EXISTS intelligence.link_score_outcomes (
    id BIGSERIAL PRIMARY KEY,
    domain_key TEXT,
    score_parts JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'desk',
    proposal_id BIGINT,
    endpoints JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_link_score_outcomes_decision CHECK (
        decision IN ('accept', 'reject', 'keep', 'demote', 'unlink', 'quarantine', 'other')
    ),
    CONSTRAINT chk_link_score_outcomes_source CHECK (
        source IN (
            'review_agent',
            'editorial',
            'membership',
            'desk',
            'embedding_link',
            'collision',
            'other'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_link_score_outcomes_domain_created
    ON intelligence.link_score_outcomes (domain_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_link_score_outcomes_source_decision
    ON intelligence.link_score_outcomes (source, decision);

COMMENT ON TABLE intelligence.link_score_outcomes IS
    'Calibration log: score_parts + human/agent accept|reject (and membership actions).';
