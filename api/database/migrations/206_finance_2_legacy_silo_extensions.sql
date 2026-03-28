-- Migration 206: finance_2 — tables that exist on legacy ``finance`` but not on the
-- migration-201 template clone (science_tech-shaped core only).
--
-- Rationale: New template silos (201) stay minimal; per-silo deltas live in follow-on
-- migrations like this so future domains are not forced to carry finance-only objects.
-- After apply, ``copy_domain_silo_table_data.py`` can copy rows for the intersection
-- of table names (see preferred order in that script).
--
-- Idempotent: CREATE IF NOT EXISTS / IF NOT EXISTS indexes and triggers.

-- UUID defaults: gen_random_uuid() is built-in PostgreSQL 13+ (no uuid-ossp).

-- ---------- Finance-specific analytics tables (parity with archived 122) ----------

CREATE TABLE IF NOT EXISTS finance_2.market_patterns (
    id SERIAL PRIMARY KEY,
    pattern_uuid UUID DEFAULT gen_random_uuid(),

    pattern_type VARCHAR(50) NOT NULL,
    pattern_name VARCHAR(200) NOT NULL,
    description TEXT,

    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    time_window_days INTEGER NOT NULL,
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

    pattern_data JSONB DEFAULT '{}',
    affected_companies TEXT[],
    affected_articles INTEGER[],
    market_impact DECIMAL(5,2),

    pattern_strength DECIMAL(3,2),
    pattern_duration_days INTEGER,
    predicted_outcome TEXT,
    actual_outcome TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS finance_2.corporate_announcements (
    id SERIAL PRIMARY KEY,
    announcement_uuid UUID DEFAULT gen_random_uuid(),

    company_name VARCHAR(200) NOT NULL,
    ticker_symbol VARCHAR(10),
    company_sector VARCHAR(100),
    company_industry VARCHAR(100),

    announcement_type VARCHAR(50) NOT NULL,
    announcement_date DATE NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    summary TEXT,

    source_url TEXT,
    source_type VARCHAR(50),
    filing_type VARCHAR(50),
    filing_date DATE,

    sentiment_score DECIMAL(3,2),
    sentiment_label VARCHAR(20),
    market_impact DECIMAL(5,2),
    impact_duration_days INTEGER,

    article_id INTEGER,
    related_announcements INTEGER[],

    raw_data JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

ALTER TABLE finance_2.corporate_announcements
    DROP CONSTRAINT IF EXISTS corporate_announcements_article_id_fkey;
ALTER TABLE finance_2.corporate_announcements
    ADD CONSTRAINT corporate_announcements_article_id_fkey
    FOREIGN KEY (article_id) REFERENCES finance_2.articles(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS finance_2.financial_indicators (
    id SERIAL PRIMARY KEY,
    indicator_uuid UUID DEFAULT gen_random_uuid(),

    company_name VARCHAR(200),
    ticker_symbol VARCHAR(10),

    indicator_type VARCHAR(50) NOT NULL,
    value DECIMAL(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    unit VARCHAR(20),

    period_start DATE,
    period_end DATE,
    period_type VARCHAR(20),
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,

    reported_at TIMESTAMP WITH TIME ZONE,
    report_source VARCHAR(100),
    report_url TEXT,

    previous_value DECIMAL(15,2),
    change_percentage DECIMAL(5,2),
    consensus_estimate DECIMAL(15,2),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_finance_2_market_patterns_type ON finance_2.market_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_finance_2_market_patterns_detected_at ON finance_2.market_patterns(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_finance_2_market_patterns_confidence ON finance_2.market_patterns(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_finance_2_market_patterns_companies ON finance_2.market_patterns USING GIN(affected_companies);

CREATE INDEX IF NOT EXISTS idx_finance_2_corporate_announcements_company ON finance_2.corporate_announcements(company_name);
CREATE INDEX IF NOT EXISTS idx_finance_2_corporate_announcements_ticker ON finance_2.corporate_announcements(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_finance_2_corporate_announcements_type ON finance_2.corporate_announcements(announcement_type);
CREATE INDEX IF NOT EXISTS idx_finance_2_corporate_announcements_date ON finance_2.corporate_announcements(announcement_date DESC);
CREATE INDEX IF NOT EXISTS idx_finance_2_corporate_announcements_sentiment ON finance_2.corporate_announcements(sentiment_score);

CREATE INDEX IF NOT EXISTS idx_finance_2_financial_indicators_company ON finance_2.financial_indicators(company_name);
CREATE INDEX IF NOT EXISTS idx_finance_2_financial_indicators_ticker ON finance_2.financial_indicators(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_finance_2_financial_indicators_type ON finance_2.financial_indicators(indicator_type);
CREATE INDEX IF NOT EXISTS idx_finance_2_financial_indicators_period ON finance_2.financial_indicators(period_start, period_end);

DROP TRIGGER IF EXISTS update_finance_2_market_patterns_updated_at ON finance_2.market_patterns;
CREATE TRIGGER update_finance_2_market_patterns_updated_at
    BEFORE UPDATE ON finance_2.market_patterns
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

DROP TRIGGER IF EXISTS update_finance_2_corporate_announcements_updated_at ON finance_2.corporate_announcements;
CREATE TRIGGER update_finance_2_corporate_announcements_updated_at
    BEFORE UPDATE ON finance_2.corporate_announcements
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

DROP TRIGGER IF EXISTS update_finance_2_financial_indicators_updated_at ON finance_2.financial_indicators;
CREATE TRIGGER update_finance_2_financial_indicators_updated_at
    BEFORE UPDATE ON finance_2.financial_indicators
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

COMMENT ON TABLE finance_2.market_patterns IS 'Detected market patterns (finance-2; parity with finance.market_patterns).';
COMMENT ON TABLE finance_2.corporate_announcements IS 'Corporate announcements (finance-2; parity with finance.corporate_announcements).';
COMMENT ON TABLE finance_2.financial_indicators IS 'Financial indicators (finance-2; parity with finance.financial_indicators).';

-- ---------- Research topics (archived 150) ----------

CREATE TABLE IF NOT EXISTS finance_2.research_topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    query TEXT NOT NULL,
    topic VARCHAR(50) NOT NULL DEFAULT 'gold',
    date_range_start DATE,
    date_range_end DATE,
    summary TEXT,
    source_task_id VARCHAR(64),
    last_refined_task_id VARCHAR(64),
    last_refined_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_finance_2_research_topics_updated
    ON finance_2.research_topics(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_finance_2_research_topics_name
    ON finance_2.research_topics(name);

COMMENT ON TABLE finance_2.research_topics IS 'Saved finance analyses for refinement (finance-2; parity with finance.research_topics).';

-- ---------- Topic extraction queue (archived 130 pattern; domain-scoped) ----------

CREATE TABLE IF NOT EXISTS finance_2.topic_extraction_queue (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES finance_2.articles(id) ON DELETE CASCADE,

    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    priority INTEGER DEFAULT 2 CHECK (priority >= 1 AND priority <= 4),

    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 10,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    next_retry_at TIMESTAMP WITH TIME ZONE,

    error_message TEXT,
    last_error TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    metadata JSONB DEFAULT '{}',

    UNIQUE(article_id)
);

CREATE INDEX IF NOT EXISTS idx_finance_2_topic_queue_status ON finance_2.topic_extraction_queue(status);
CREATE INDEX IF NOT EXISTS idx_finance_2_topic_queue_priority ON finance_2.topic_extraction_queue(priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_finance_2_topic_queue_retry ON finance_2.topic_extraction_queue(next_retry_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_finance_2_topic_queue_article ON finance_2.topic_extraction_queue(article_id);

DO $$
BEGIN
  RAISE NOTICE 'Migration 206: finance_2 legacy silo extensions (market_patterns, corporate_announcements, financial_indicators, research_topics, topic_extraction_queue)';
END $$;
