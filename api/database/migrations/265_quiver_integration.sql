-- Migration 265: Quiver Quantitative API Integration
-- Core tables for congressional trades, government contracts, lobbying, and insider trades
-- Politician entity profiles for domain_key='politics'

-- 1. Congressional Trades (primary dataset)
CREATE TABLE IF NOT EXISTS intelligence.quiver_congress_trades (
    id BIGSERIAL PRIMARY KEY,
    quiver_trade_id TEXT UNIQUE NOT NULL,
    politician_name TEXT NOT NULL,
    politician_bioguide_id TEXT,
    chamber TEXT,  -- 'Senate' or 'House'
    party TEXT,
    state TEXT,
    ticker TEXT NOT NULL,
    company_name TEXT,
    transaction_type TEXT,  -- 'Purchase', 'Sale', 'Exchange', 'Partial Sale'
    amount_range TEXT,  -- '$1,001 - $15,000'
    traded_date DATE,
    filed_date DATE,
    owner_type TEXT,  -- 'Self', 'Spouse', 'Dependent', 'Joint'
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiver_congress_trades_politician
    ON intelligence.quiver_congress_trades (politician_name);
CREATE INDEX IF NOT EXISTS idx_quiver_congress_trades_ticker
    ON intelligence.quiver_congress_trades (ticker);
CREATE INDEX IF NOT EXISTS idx_quiver_congress_trades_filed
    ON intelligence.quiver_congress_trades (filed_date DESC);
CREATE INDEX IF NOT EXISTS idx_quiver_congress_trades_chamber_party
    ON intelligence.quiver_congress_trades (chamber, party);
CREATE INDEX IF NOT EXISTS idx_quiver_congress_trades_bioguide
    ON intelligence.quiver_congress_trades (politician_bioguide_id);

COMMENT ON TABLE intelligence.quiver_congress_trades IS
    'Congressional stock trades from Quiver Quantitative API. Updated daily via collector.';

-- 2. Government Contracts
CREATE TABLE IF NOT EXISTS intelligence.quiver_gov_contracts (
    id BIGSERIAL PRIMARY KEY,
    quiver_contract_id TEXT UNIQUE NOT NULL,
    ticker TEXT,
    company_name TEXT,
    agency TEXT,
    award_amount NUMERIC,
    award_date DATE,
    description TEXT,
    contract_type TEXT,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiver_gov_contracts_ticker
    ON intelligence.quiver_gov_contracts (ticker);
CREATE INDEX IF NOT EXISTS idx_quiver_gov_contracts_agency
    ON intelligence.quiver_gov_contracts (agency);
CREATE INDEX IF NOT EXISTS idx_quiver_gov_contracts_award_date
    ON intelligence.quiver_gov_contracts (award_date DESC);

COMMENT ON TABLE intelligence.quiver_gov_contracts IS
    'US Government contracts to public companies from Quiver Quantitative API.';

-- 3. Corporate Lobbying
CREATE TABLE IF NOT EXISTS intelligence.quiver_lobbying (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT,
    client_name TEXT,
    amount NUMERIC,
    year INTEGER,
    quarter INTEGER,
    issues TEXT[],
    lobbyists TEXT[],
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiver_lobbying_ticker
    ON intelligence.quiver_lobbying (ticker);
CREATE INDEX IF NOT EXISTS idx_quiver_lobbying_client
    ON intelligence.quiver_lobbying (client_name);
CREATE INDEX IF NOT EXISTS idx_quiver_lobbying_year_quarter
    ON intelligence.quiver_lobbying (year DESC, quarter DESC);

COMMENT ON TABLE intelligence.quiver_lobbying IS
    'Corporate lobbying expenditures from Quiver Quantitative API.';

-- 4. Insider Trades
CREATE TABLE IF NOT EXISTS intelligence.quiver_insider_trades (
    id BIGSERIAL PRIMARY KEY,
    quiver_trade_id TEXT UNIQUE NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT,
    insider_name TEXT,
    insider_title TEXT,
    transaction_type TEXT,  -- 'Purchase', 'Sale', 'Exercise', 'Conversion'
    shares BIGINT,
    price_per_share NUMERIC,
    transaction_date DATE,
    filing_date DATE,
    ownership_type TEXT,  -- 'Direct', 'Indirect'
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiver_insider_trades_ticker
    ON intelligence.quiver_insider_trades (ticker);
CREATE INDEX IF NOT EXISTS idx_quiver_insider_trades_insider
    ON intelligence.quiver_insider_trades (insider_name);
CREATE INDEX IF NOT EXISTS idx_quiver_insider_trades_date
    ON intelligence.quiver_insider_trades (transaction_date DESC);

COMMENT ON TABLE intelligence.quiver_insider_trades IS
    'Corporate insider transactions from Quiver Quantitative API.';

-- 5. Politician Entity Profiles (domain_key='politics')
-- Ensure politicians from congress trades are resolvable as entities
DO $$
BEGIN
    -- Check if politics domain exists in public.domains
    IF EXISTS (SELECT 1 FROM public.domains WHERE key = 'politics') THEN
        -- Politicians are stored as entity_profiles with domain_key='politics'
        -- Metadata fields: bioguide_id, chamber, party, state, source='quiver_congress'
        RAISE NOTICE 'Politics domain exists - politicians will be linked via entity_profiles';
    ELSE
        RAISE NOTICE 'Politics domain not found - ensure domain is registered';
    END IF;
END $$;

-- View for politician trading summary
CREATE OR REPLACE VIEW intelligence.quiver_politician_trade_summary AS
SELECT
    politician_name,
    politician_bioguide_id,
    chamber,
    party,
    state,
    COUNT(*) as total_trades,
    COUNT(DISTINCT ticker) as unique_tickers,
    MIN(filed_date) as first_trade_date,
    MAX(filed_date) as latest_trade_date,
    SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
    SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales,
    SUM(CASE WHEN transaction_type ILIKE '%exchange%' THEN 1 ELSE 0 END) as exchanges
FROM intelligence.quiver_congress_trades
GROUP BY politician_name, politician_bioguide_id, chamber, party, state
ORDER BY total_trades DESC;

COMMENT ON VIEW intelligence.quiver_politician_trade_summary IS
    'Aggregated trading activity per politician for dashboard/analytics.';

-- View for most traded tickers by Congress
CREATE OR REPLACE VIEW intelligence.quiver_ticker_congress_activity AS
SELECT
    ticker,
    company_name,
    COUNT(*) as total_trades,
    COUNT(DISTINCT politician_name) as unique_politicians,
    COUNT(DISTINCT politician_bioguide_id) as unique_politicians_id,
    SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
    SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales,
    MAX(filed_date) as latest_trade_date
FROM intelligence.quiver_congress_trades
GROUP BY ticker, company_name
ORDER BY total_trades DESC;

COMMENT ON VIEW intelligence.quiver_ticker_congress_activity IS
    'Most actively traded stocks by Congress members.';

DO $$
BEGIN
    RAISE NOTICE 'Migration 265: Quiver integration tables created';
END $$;