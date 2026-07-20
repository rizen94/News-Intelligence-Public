-- Migration 271: Narrative inference roadmap (E/A/B/C)
-- Phase E: phase silence + backlog snapshot history
-- Phase A: typed causal edges
-- Phase B: rolling 12-month arcs
-- Phase C: event→ticker impacts + HITL trading signals

-- ---------------------------------------------------------------------------
-- Phase E — ops
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.phase_silence_state (
    phase_name TEXT PRIMARY KEY,
    silenced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT NOT NULL DEFAULT '',
    health_status TEXT,
    failing_streak INT NOT NULL DEFAULT 0,
    auto_silenced BOOLEAN NOT NULL DEFAULT TRUE,
    cleared_at TIMESTAMPTZ,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.phase_silence_state IS
    'Config-driven auto-silence for brittle pipeline phases (Phase E). Cleared rows keep history via cleared_at.';

CREATE TABLE IF NOT EXISTS intelligence.monitor_backlog_snapshot_history (
    id BIGSERIAL PRIMARY KEY,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    elapsed_ms INT,
    phase_count INT,
    queue_depths JSONB NOT NULL DEFAULT '{}'::jsonb,
    backlog_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_monitor_backlog_snapshot_history_refreshed
    ON intelligence.monitor_backlog_snapshot_history (refreshed_at DESC);

COMMENT ON TABLE intelligence.monitor_backlog_snapshot_history IS
    'Time-series of Monitor backlog snapshots for p95/read-mostly paths (Phase E).';

-- ---------------------------------------------------------------------------
-- Phase A — typed causal edges
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS intelligence.causal_edges (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cause_kind TEXT NOT NULL,
    cause_id BIGINT NOT NULL,
    effect_kind TEXT NOT NULL,
    effect_id BIGINT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'contributes_to',
    confidence REAL NOT NULL DEFAULT 0.5,
    evidence_grade TEXT NOT NULL DEFAULT 'weak',
    evidence_context_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    reasoning_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    domain_key TEXT,
    source TEXT NOT NULL DEFAULT 'editorial_room',
    source_proposal_id BIGINT,
    status TEXT NOT NULL DEFAULT 'active',
    CONSTRAINT uq_causal_edge_endpoints UNIQUE (
        cause_kind, cause_id, effect_kind, effect_id, relation
    ),
    CONSTRAINT chk_causal_edge_kinds CHECK (
        cause_kind IN ('tracked_event', 'chronological_event', 'storyline', 'entity', 'context')
        AND effect_kind IN ('tracked_event', 'chronological_event', 'storyline', 'entity', 'context')
    ),
    CONSTRAINT chk_causal_evidence_grade CHECK (
        evidence_grade IN ('strong', 'moderate', 'weak', 'speculative')
    )
);

CREATE INDEX IF NOT EXISTS idx_causal_edges_cause
    ON intelligence.causal_edges (cause_kind, cause_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_causal_edges_effect
    ON intelligence.causal_edges (effect_kind, effect_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_causal_edges_domain
    ON intelligence.causal_edges (domain_key) WHERE status = 'active';

COMMENT ON TABLE intelligence.causal_edges IS
    'Typed evidence-graded causal edges. Postgres is write SSOT; Neo4j may project for traversal.';

-- ---------------------------------------------------------------------------
-- Phase B — rolling 12-month arcs
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS intelligence.rolling_arcs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    material_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    domain_key TEXT NOT NULL,
    theme_key TEXT NOT NULL,
    title TEXT NOT NULL,
    arc_type TEXT NOT NULL DEFAULT 'rolling_12m',
    window_days INT NOT NULL DEFAULT 365,
    strength REAL NOT NULL DEFAULT 0.0,
    summary TEXT,
    chapters JSONB NOT NULL DEFAULT '[]'::jsonb,
    storyline_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    chronological_event_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    latent_proposal_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_rolling_arc_theme UNIQUE (domain_key, theme_key, arc_type)
);

CREATE INDEX IF NOT EXISTS idx_rolling_arcs_domain_status
    ON intelligence.rolling_arcs (domain_key, status, material_updated_at DESC);

COMMENT ON TABLE intelligence.rolling_arcs IS
    'Mid-horizon rolling arcs (default 12m) distinct from curated historical_arcs.yaml.';

-- ---------------------------------------------------------------------------
-- Phase C — trading signals
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS intelligence.entity_ticker_map (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entity_id BIGINT,
    entity_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    exchange TEXT,
    domain_key TEXT DEFAULT 'finance',
    source TEXT NOT NULL DEFAULT 'manual',
    confidence REAL NOT NULL DEFAULT 0.8,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_ticker_entity
    ON intelligence.entity_ticker_map (entity_id, ticker)
    WHERE entity_id IS NOT NULL AND active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_ticker_name
    ON intelligence.entity_ticker_map (lower(entity_name), ticker)
    WHERE entity_id IS NULL AND active;

CREATE TABLE IF NOT EXISTS intelligence.event_ticker_impacts (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tracked_event_id BIGINT,
    chronological_event_id BIGINT,
    causal_edge_id BIGINT REFERENCES intelligence.causal_edges (id) ON DELETE SET NULL,
    ticker TEXT NOT NULL,
    expected_move_pct REAL,
    confidence REAL NOT NULL DEFAULT 0.4,
    method TEXT NOT NULL DEFAULT 'heuristic',
    direction TEXT NOT NULL DEFAULT 'unknown',
    rationale TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'proposed'
);

CREATE INDEX IF NOT EXISTS idx_event_ticker_impacts_event
    ON intelligence.event_ticker_impacts (tracked_event_id, status);
CREATE INDEX IF NOT EXISTS idx_event_ticker_impacts_ticker
    ON intelligence.event_ticker_impacts (ticker, status);

CREATE TABLE IF NOT EXISTS intelligence.trading_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    impact_id BIGINT REFERENCES intelligence.event_ticker_impacts (id) ON DELETE SET NULL,
    ticker TEXT NOT NULL,
    idea_summary TEXT NOT NULL,
    expected_move_pct REAL,
    confidence REAL NOT NULL DEFAULT 0.4,
    review_status TEXT NOT NULL DEFAULT 'pending',
    review_reason TEXT,
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_trading_signal_review CHECK (
        review_status IN ('pending', 'approved', 'rejected')
    )
);

CREATE INDEX IF NOT EXISTS idx_trading_signals_review
    ON intelligence.trading_signals (review_status, created_at DESC);

COMMENT ON TABLE intelligence.trading_signals IS
    'HITL trade ideas from event→ticker impact. No auto-execution.';

DO $$
BEGIN
    RAISE NOTICE 'Migration 271: narrative inference tables created (phase silence, backlog history, causal_edges, rolling_arcs, signals)';
END $$;
