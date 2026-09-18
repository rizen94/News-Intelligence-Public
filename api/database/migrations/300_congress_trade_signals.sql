-- Migration 300: Congressional trade signals (Quiver enrich → score → paper → HITL)
-- Intelligence + HITL product only — no live brokerage.
-- Requires migration 265 (intelligence.quiver_congress_trades).

CREATE TABLE IF NOT EXISTS intelligence.congress_trade_enrichment (
    quiver_trade_id TEXT PRIMARY KEY
        REFERENCES intelligence.quiver_congress_trades (quiver_trade_id) ON DELETE CASCADE,
    lag_days INTEGER,
    amount_bucket_mid NUMERIC,
    amount_ordinal SMALLINT,
    side TEXT NOT NULL DEFAULT 'other',
    committee_ids TEXT[] NOT NULL DEFAULT '{}',
    committee_names TEXT[] NOT NULL DEFAULT '{}',
    issuer_sector TEXT,
    leadership_weight REAL NOT NULL DEFAULT 1.0,
    bipartisan_cluster_id TEXT,
    disclosure_freshness_days INTEGER,
    enrichment_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    enriched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_congress_enrichment_side CHECK (side IN ('buy', 'sell', 'other'))
);

CREATE INDEX IF NOT EXISTS idx_congress_trade_enrichment_side
    ON intelligence.congress_trade_enrichment (side);
CREATE INDEX IF NOT EXISTS idx_congress_trade_enrichment_sector
    ON intelligence.congress_trade_enrichment (issuer_sector);
CREATE INDEX IF NOT EXISTS idx_congress_trade_enrichment_cluster
    ON intelligence.congress_trade_enrichment (bipartisan_cluster_id)
    WHERE bipartisan_cluster_id IS NOT NULL;

COMMENT ON TABLE intelligence.congress_trade_enrichment IS
    'Deterministic enrichment of Quiver congress trades (lag, size, committees, clusters).';

CREATE TABLE IF NOT EXISTS intelligence.congress_trade_signals (
    id BIGSERIAL PRIMARY KEY,
    quiver_trade_id TEXT NOT NULL UNIQUE
        REFERENCES intelligence.quiver_congress_trades (quiver_trade_id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    signal_score REAL NOT NULL,
    score_parts JSONB NOT NULL DEFAULT '{}'::jsonb,
    eligible BOOLEAN NOT NULL DEFAULT FALSE,
    paper_weight REAL,
    as_of_date DATE NOT NULL,
    hitl_signal_id BIGINT REFERENCES intelligence.trading_signals (id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_congress_trade_signals_eligible_score
    ON intelligence.congress_trade_signals (eligible, signal_score DESC)
    WHERE eligible = TRUE;
CREATE INDEX IF NOT EXISTS idx_congress_trade_signals_as_of
    ON intelligence.congress_trade_signals (as_of_date DESC);
CREATE INDEX IF NOT EXISTS idx_congress_trade_signals_ticker
    ON intelligence.congress_trade_signals (ticker, as_of_date DESC);

COMMENT ON TABLE intelligence.congress_trade_signals IS
    'Scored congress trade ideas. as_of_date = disclosure filed_date only (no look-ahead).';

CREATE TABLE IF NOT EXISTS intelligence.congress_paper_positions (
    id BIGSERIAL PRIMARY KEY,
    as_of_month DATE NOT NULL,
    ticker TEXT NOT NULL,
    weight REAL NOT NULL,
    side TEXT NOT NULL DEFAULT 'long',
    signal_ids BIGINT[] NOT NULL DEFAULT '{}',
    sector TEXT,
    entry_price NUMERIC,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (as_of_month, ticker),
    CONSTRAINT chk_congress_paper_side CHECK (side IN ('long', 'flat'))
);

CREATE INDEX IF NOT EXISTS idx_congress_paper_positions_month
    ON intelligence.congress_paper_positions (as_of_month DESC);

COMMENT ON TABLE intelligence.congress_paper_positions IS
    'Monthly paper portfolio positions from eligible congress signals (disclosure-dated).';

CREATE TABLE IF NOT EXISTS intelligence.congress_paper_nav (
    id BIGSERIAL PRIMARY KEY,
    as_of_date DATE NOT NULL UNIQUE,
    nav REAL NOT NULL,
    spy_nav REAL,
    cash_weight REAL NOT NULL DEFAULT 0,
    positions_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_congress_paper_nav_date
    ON intelligence.congress_paper_nav (as_of_date DESC);

COMMENT ON TABLE intelligence.congress_paper_nav IS
    'Daily/monthly paper NAV vs SPY for congress trade strategy (no live execution).';

DO $$
BEGIN
    RAISE NOTICE 'Migration 300: congress trade enrichment/signals/paper tables created';
END $$;
