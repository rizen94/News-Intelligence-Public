-- Migration 279: Narrative Enhancement Phases 5–6
-- Arc intelligence scaffolding + UX differentiators (expectations, outcomes).
-- (Was briefly numbered 278; 278 is reserved for link_score_outcomes.)

-- ---------------------------------------------------------------------------
-- Stimulus RAG: generalize beyond arXiv
-- ---------------------------------------------------------------------------

ALTER TABLE intelligence.rag_evidence_pull_queue
    ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'arxiv';

ALTER TABLE intelligence.rag_evidence_pull_queue
    DROP CONSTRAINT IF EXISTS rag_evidence_pull_queue_source_type_check;

ALTER TABLE intelligence.rag_evidence_pull_queue
    ADD CONSTRAINT rag_evidence_pull_queue_source_type_check
    CHECK (source_type IN (
        'arxiv',
        'court_pdf',
        'federal_register',
        'who_cdc',
        'url_fetch',
        'other'
    ));

CREATE INDEX IF NOT EXISTS idx_rag_evidence_pull_source_type
    ON intelligence.rag_evidence_pull_queue (source_type, status, created_at DESC);

COMMENT ON COLUMN intelligence.rag_evidence_pull_queue.source_type IS
    'Evidence source family for stimulus RAG (arxiv, court_pdf, federal_register, who_cdc).';

-- ---------------------------------------------------------------------------
-- Expectation tracking (C3)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS intelligence.narrative_expectations (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    domain_key TEXT NOT NULL,
    storyline_id BIGINT,
    source_claim_id BIGINT,
    context_id BIGINT,
    claim_text TEXT NOT NULL,
    subject_text TEXT,
    expected_outcome TEXT,
    due_date DATE,
    due_date_precision TEXT NOT NULL DEFAULT 'day'
        CHECK (due_date_precision IN ('day', 'week', 'month', 'quarter', 'year', 'unknown')),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN (
            'open',
            'due_soon',
            'overdue',
            'resolved',
            'expired',
            'cancelled'
        )),
    resolved_at TIMESTAMPTZ,
    outcome_event_id BIGINT,
    outcome_summary TEXT,
    confidence REAL NOT NULL DEFAULT 0.5,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_narrative_expectations_status_due
    ON intelligence.narrative_expectations (status, due_date)
    WHERE status IN ('open', 'due_soon', 'overdue');

CREATE INDEX IF NOT EXISTS idx_narrative_expectations_domain
    ON intelligence.narrative_expectations (domain_key, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_narrative_expectations_claim
    ON intelligence.narrative_expectations (source_claim_id)
    WHERE source_claim_id IS NOT NULL;

COMMENT ON TABLE intelligence.narrative_expectations IS
    'Forward-looking claims with due dates (Phase 6 C3 expectation tracking).';

-- ---------------------------------------------------------------------------
-- Trading signal outcome writeback (C10)
-- ---------------------------------------------------------------------------

ALTER TABLE intelligence.trading_signals
    ADD COLUMN IF NOT EXISTS actual_move_pct REAL;

ALTER TABLE intelligence.trading_signals
    ADD COLUMN IF NOT EXISTS outcome_scored_at TIMESTAMPTZ;

ALTER TABLE intelligence.trading_signals
    ADD COLUMN IF NOT EXISTS outcome_source TEXT;

ALTER TABLE intelligence.trading_signals
    ADD COLUMN IF NOT EXISTS outcome_score REAL;

COMMENT ON COLUMN intelligence.trading_signals.actual_move_pct IS
    'Retrospective Stooq/market move used to score the signal.';
COMMENT ON COLUMN intelligence.trading_signals.outcome_score IS
    'Directional correctness score in [-1, 1] vs expected move.';

DO $$
BEGIN
    RAISE NOTICE 'Migration 279: narrative expectations + stimulus source_type + trading outcomes';
END $$;
