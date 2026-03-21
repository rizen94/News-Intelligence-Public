-- Migration 122: Domain Silo Infrastructure for v4.0
-- Creates multi-domain architecture with schema-based isolation
-- Created: December 7, 2025
-- Version: 4.0.0

-- ============================================================================
-- PHASE 1: DOMAIN INFRASTRUCTURE SETUP
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================================
-- DOMAIN CONFIGURATION (Public Schema)
-- ============================================================================

-- Domains configuration table (in public schema for cross-domain access)
CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) UNIQUE NOT NULL,  -- 'politics', 'finance', 'science-tech'
    name VARCHAR(100) NOT NULL,              -- 'Politics', 'Finance', 'Science & Technology'
    description TEXT,
    schema_name VARCHAR(50) NOT NULL,         -- 'politics', 'finance', 'science_tech'
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    config JSONB DEFAULT '{}',              -- Domain-specific configuration
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_domain_key CHECK (domain_key ~ '^[a-z0-9-]+$'),
    CONSTRAINT valid_schema_name CHECK (schema_name ~ '^[a-z0-9_]+$')
);

-- Indexes for domains table
CREATE INDEX IF NOT EXISTS idx_domains_key ON domains(domain_key);
CREATE INDEX IF NOT EXISTS idx_domains_active ON domains(is_active);
CREATE INDEX IF NOT EXISTS idx_domains_display_order ON domains(display_order);

-- Domain metadata table for tracking domain statistics
CREATE TABLE IF NOT EXISTS domain_metadata (
    domain_id INTEGER PRIMARY KEY REFERENCES domains(id) ON DELETE CASCADE,
    article_count INTEGER DEFAULT 0,
    topic_count INTEGER DEFAULT 0,
    storyline_count INTEGER DEFAULT 0,
    feed_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default domains
INSERT INTO domains (domain_key, name, schema_name, display_order, description) VALUES
('politics', 'Politics', 'politics', 1, 'Political news, government, elections, and policy analysis'),
('finance', 'Finance', 'finance', 2, 'Financial markets, corporate announcements, market research, and economic analysis'),
('science-tech', 'Science & Technology', 'science_tech', 3, 'Scientific research, technology news, innovation, and industry analysis')
ON CONFLICT (domain_key) DO NOTHING;

-- ============================================================================
-- CREATE DOMAIN SCHEMAS
-- ============================================================================

-- Create schemas for each domain
CREATE SCHEMA IF NOT EXISTS politics;
CREATE SCHEMA IF NOT EXISTS finance;
CREATE SCHEMA IF NOT EXISTS science_tech;

-- Grant permissions
GRANT USAGE ON SCHEMA politics TO newsapp;
GRANT USAGE ON SCHEMA finance TO newsapp;
GRANT USAGE ON SCHEMA science_tech TO newsapp;

-- Grant create privileges for future migrations
GRANT CREATE ON SCHEMA politics TO newsapp;
GRANT CREATE ON SCHEMA finance TO newsapp;
GRANT CREATE ON SCHEMA science_tech TO newsapp;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA politics GRANT ALL ON TABLES TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA finance GRANT ALL ON TABLES TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA science_tech GRANT ALL ON TABLES TO newsapp;

-- ============================================================================
-- HELPER FUNCTION: Create table structure from existing table
-- ============================================================================

CREATE OR REPLACE FUNCTION create_domain_table(
    target_schema TEXT,
    table_name_param TEXT,
    source_schema TEXT DEFAULT 'public'
)
RETURNS VOID AS $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    -- Check if source table exists
    SELECT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = source_schema 
        AND information_schema.tables.table_name = table_name_param
    ) INTO table_exists;
    
    IF table_exists THEN
        -- Create table with same structure as source
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.%I (
                LIKE %I.%I INCLUDING ALL
            )',
            target_schema, table_name_param, source_schema, table_name_param
        );
    ELSE
        -- Table doesn't exist, skip it
        RAISE NOTICE 'Source table %.% does not exist, skipping', source_schema, table_name_param;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- POLITICS SCHEMA TABLES
-- ============================================================================

-- Articles table
SELECT create_domain_table('politics', 'articles', 'public');

-- Topics table (create if doesn't exist in public)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'topics') THEN
        SELECT create_domain_table('politics', 'topics', 'public');
    ELSE
        -- Create topics table structure (from migration 121)
        CREATE TABLE IF NOT EXISTS politics.topics (
            id SERIAL PRIMARY KEY,
            topic_uuid UUID DEFAULT uuid_generate_v4(),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            keywords TEXT[],
            confidence_score DECIMAL(3,2) DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
            accuracy_score DECIMAL(3,2) DEFAULT 0.5 CHECK (accuracy_score >= 0.0 AND accuracy_score <= 1.0),
            review_count INTEGER DEFAULT 0,
            correct_assignments INTEGER DEFAULT 0,
            incorrect_assignments INTEGER DEFAULT 0,
            learning_data JSONB DEFAULT '{}',
            last_improved_at TIMESTAMP WITH TIME ZONE,
            improvement_trend DECIMAL(3,2) DEFAULT 0.0,
            status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'reviewed', 'archived', 'merged')),
            is_auto_generated BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(100),
            CONSTRAINT unique_topic_name UNIQUE (name)
        );
    END IF;
END $$;

-- Storylines table
SELECT create_domain_table('politics', 'storylines', 'public');

-- RSS Feeds table
SELECT create_domain_table('politics', 'rss_feeds', 'public');

-- Article-Topic Assignments (create if doesn't exist in public)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'article_topic_assignments') THEN
        SELECT create_domain_table('politics', 'article_topic_assignments', 'public');
    ELSE
        -- Create article_topic_assignments table structure (from migration 121)
        CREATE TABLE IF NOT EXISTS politics.article_topic_assignments (
            id SERIAL PRIMARY KEY,
            assignment_uuid UUID DEFAULT uuid_generate_v4(),
            article_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL,
            confidence_score DECIMAL(3,2) DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
            relevance_score DECIMAL(3,2) DEFAULT 0.5 CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0),
            is_validated BOOLEAN DEFAULT FALSE,
            is_correct BOOLEAN,
            feedback_notes TEXT,
            feedback_source VARCHAR(50),
            assignment_method VARCHAR(50) DEFAULT 'auto' CHECK (assignment_method IN ('auto', 'manual', 'learned', 'hybrid')),
            model_version VARCHAR(50),
            assignment_context JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            validated_at TIMESTAMP WITH TIME ZONE,
            validated_by VARCHAR(100),
            CONSTRAINT unique_article_topic UNIQUE (article_id, topic_id),
            CONSTRAINT article_topic_assignments_article_id_fkey FOREIGN KEY (article_id) REFERENCES politics.articles(id) ON DELETE CASCADE,
            CONSTRAINT article_topic_assignments_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES politics.topics(id) ON DELETE CASCADE
        );
    END IF;
END $$;

-- Storyline Articles
SELECT create_domain_table('politics', 'storyline_articles', 'public');

-- Topic Clusters
SELECT create_domain_table('politics', 'topic_clusters', 'public');

-- Topic Cluster Memberships (create if doesn't exist in public)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'topic_cluster_memberships') THEN
        SELECT create_domain_table('politics', 'topic_cluster_memberships', 'public');
    ELSE
        CREATE TABLE IF NOT EXISTS politics.topic_cluster_memberships (
            id SERIAL PRIMARY KEY,
            topic_id INTEGER NOT NULL,
            cluster_id INTEGER NOT NULL,
            membership_confidence DECIMAL(3,2) DEFAULT 0.5,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_topic_cluster UNIQUE (topic_id, cluster_id),
            CONSTRAINT topic_cluster_memberships_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES politics.topics(id) ON DELETE CASCADE,
            CONSTRAINT topic_cluster_memberships_cluster_id_fkey FOREIGN KEY (cluster_id) REFERENCES politics.topic_clusters(id) ON DELETE CASCADE
        );
    END IF;
END $$;

-- Topic Learning History (create if doesn't exist in public)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'topic_learning_history') THEN
        SELECT create_domain_table('politics', 'topic_learning_history', 'public');
    ELSE
        CREATE TABLE IF NOT EXISTS politics.topic_learning_history (
            id SERIAL PRIMARY KEY,
            topic_id INTEGER NOT NULL,
            event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('review', 'correction', 'validation', 'improvement')),
            event_data JSONB DEFAULT '{}',
            accuracy_before DECIMAL(3,2),
            accuracy_after DECIMAL(3,2),
            confidence_before DECIMAL(3,2),
            confidence_after DECIMAL(3,2),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(100),
            CONSTRAINT topic_learning_history_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES politics.topics(id) ON DELETE CASCADE
        );
    END IF;
END $$;

-- ============================================================================
-- FINANCE SCHEMA TABLES
-- ============================================================================

-- Base tables (same as politics) - use politics schema as template
SELECT create_domain_table('finance', 'articles', 'politics');
SELECT create_domain_table('finance', 'topics', 'politics');
SELECT create_domain_table('finance', 'storylines', 'politics');
SELECT create_domain_table('finance', 'rss_feeds', 'politics');
SELECT create_domain_table('finance', 'article_topic_assignments', 'politics');
SELECT create_domain_table('finance', 'storyline_articles', 'politics');
SELECT create_domain_table('finance', 'topic_clusters', 'politics');
SELECT create_domain_table('finance', 'topic_cluster_memberships', 'politics');
SELECT create_domain_table('finance', 'topic_learning_history', 'politics');

-- Finance-specific tables
CREATE TABLE IF NOT EXISTS finance.market_patterns (
    id SERIAL PRIMARY KEY,
    pattern_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Pattern Information
    pattern_type VARCHAR(50) NOT NULL,  -- 'price_trend', 'volume_spike', 'correlation', 'sentiment_shift', etc.
    pattern_name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Detection Details
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    time_window_days INTEGER NOT NULL,  -- Days of data analyzed
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    
    -- Pattern Data
    pattern_data JSONB DEFAULT '{}',  -- Pattern-specific data (trends, correlations, etc.)
    affected_companies TEXT[],        -- Array of company names
    affected_articles INTEGER[],      -- Array of article IDs from finance.articles
    market_impact DECIMAL(5,2),       -- Percentage impact on market
    
    -- Analysis Results
    pattern_strength DECIMAL(3,2),    -- How strong the pattern is
    pattern_duration_days INTEGER,     -- How long pattern has been active
    predicted_outcome TEXT,           -- AI prediction of outcome
    actual_outcome TEXT,              -- Actual outcome (filled later)
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS finance.corporate_announcements (
    id SERIAL PRIMARY KEY,
    announcement_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Company Information
    company_name VARCHAR(200) NOT NULL,
    ticker_symbol VARCHAR(10),
    company_sector VARCHAR(100),
    company_industry VARCHAR(100),
    
    -- Announcement Details
    announcement_type VARCHAR(50) NOT NULL,  -- 'earnings', 'merger', 'product', 'executive', 'regulatory', 'guidance'
    announcement_date DATE NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    summary TEXT,  -- AI-generated summary
    
    -- Source Information
    source_url TEXT,
    source_type VARCHAR(50),  -- 'sec_filing', 'press_release', 'news_article', 'corporate_website'
    filing_type VARCHAR(50),   -- For SEC filings: '10-K', '10-Q', '8-K', 'DEF 14A', etc.
    filing_date DATE,          -- For SEC filings
    
    -- Analysis
    sentiment_score DECIMAL(3,2),  -- -1.0 to 1.0
    sentiment_label VARCHAR(20),  -- 'positive', 'negative', 'neutral'
    market_impact DECIMAL(5,2),   -- Percentage price change
    impact_duration_days INTEGER, -- How long impact lasted
    
    -- Relationships
    article_id INTEGER,             -- Link to finance.articles if from news
    related_announcements INTEGER[], -- Array of related announcement IDs
    
    -- Raw Data
    raw_data JSONB,                 -- Original announcement data
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS finance.financial_indicators (
    id SERIAL PRIMARY KEY,
    indicator_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Company Information
    company_name VARCHAR(200),
    ticker_symbol VARCHAR(10),
    
    -- Indicator Details
    indicator_type VARCHAR(50) NOT NULL,  -- 'revenue', 'profit', 'market_cap', 'pe_ratio', 'dividend_yield', etc.
    value DECIMAL(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    unit VARCHAR(20),  -- 'millions', 'billions', 'per_share', 'percentage', etc.
    
    -- Time Period
    period_start DATE,
    period_end DATE,
    period_type VARCHAR(20),  -- 'quarterly', 'annual', 'ytd', 'ttm'
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    
    -- Reporting
    reported_at TIMESTAMP WITH TIME ZONE,
    report_source VARCHAR(100),  -- 'sec_filing', 'earnings_call', 'press_release'
    report_url TEXT,
    
    -- Comparison
    previous_value DECIMAL(15,2),  -- Previous period value
    change_percentage DECIMAL(5,2),  -- Percentage change
    consensus_estimate DECIMAL(15,2),  -- Analyst consensus
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- SCIENCE & TECHNOLOGY SCHEMA TABLES
-- ============================================================================

-- Base tables (same as politics) - use politics schema as template
SELECT create_domain_table('science_tech', 'articles', 'politics');
SELECT create_domain_table('science_tech', 'topics', 'politics');
SELECT create_domain_table('science_tech', 'storylines', 'politics');
SELECT create_domain_table('science_tech', 'rss_feeds', 'politics');
SELECT create_domain_table('science_tech', 'article_topic_assignments', 'politics');
SELECT create_domain_table('science_tech', 'storyline_articles', 'politics');
SELECT create_domain_table('science_tech', 'topic_clusters', 'politics');
SELECT create_domain_table('science_tech', 'topic_cluster_memberships', 'politics');
SELECT create_domain_table('science_tech', 'topic_learning_history', 'politics');

-- ============================================================================
-- FOREIGN KEY CONSTRAINTS FOR DOMAIN SCHEMAS
-- ============================================================================

-- Note: Foreign keys will be added after data migration
-- This ensures referential integrity within each domain schema

-- Function to add foreign keys for a domain schema
CREATE OR REPLACE FUNCTION add_domain_foreign_keys(schema_name TEXT)
RETURNS VOID AS $$
BEGIN
    -- Article-Topic Assignments foreign keys
    EXECUTE format('
        ALTER TABLE %I.article_topic_assignments
        DROP CONSTRAINT IF EXISTS article_topic_assignments_article_id_fkey;
        
        ALTER TABLE %I.article_topic_assignments
        ADD CONSTRAINT article_topic_assignments_article_id_fkey
        FOREIGN KEY (article_id) REFERENCES %I.articles(id) ON DELETE CASCADE;
        
        ALTER TABLE %I.article_topic_assignments
        DROP CONSTRAINT IF EXISTS article_topic_assignments_topic_id_fkey;
        
        ALTER TABLE %I.article_topic_assignments
        ADD CONSTRAINT article_topic_assignments_topic_id_fkey
        FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
    
    -- Storyline Articles foreign keys
    EXECUTE format('
        ALTER TABLE %I.storyline_articles
        DROP CONSTRAINT IF EXISTS storyline_articles_storyline_id_fkey;
        
        ALTER TABLE %I.storyline_articles
        ADD CONSTRAINT storyline_articles_storyline_id_fkey
        FOREIGN KEY (storyline_id) REFERENCES %I.storylines(id) ON DELETE CASCADE;
        
        ALTER TABLE %I.storyline_articles
        DROP CONSTRAINT IF EXISTS storyline_articles_article_id_fkey;
        
        ALTER TABLE %I.storyline_articles
        ADD CONSTRAINT storyline_articles_article_id_fkey
        FOREIGN KEY (article_id) REFERENCES %I.articles(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
    
    -- Topic Learning History foreign keys
    EXECUTE format('
        ALTER TABLE %I.topic_learning_history
        DROP CONSTRAINT IF EXISTS topic_learning_history_topic_id_fkey;
        
        ALTER TABLE %I.topic_learning_history
        ADD CONSTRAINT topic_learning_history_topic_id_fkey
        FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name);
    
    -- Topic Cluster Memberships foreign keys
    EXECUTE format('
        ALTER TABLE %I.topic_cluster_memberships
        DROP CONSTRAINT IF EXISTS topic_cluster_memberships_topic_id_fkey;
        
        ALTER TABLE %I.topic_cluster_memberships
        ADD CONSTRAINT topic_cluster_memberships_topic_id_fkey
        FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;
        
        ALTER TABLE %I.topic_cluster_memberships
        DROP CONSTRAINT IF EXISTS topic_cluster_memberships_cluster_id_fkey;
        
        ALTER TABLE %I.topic_cluster_memberships
        ADD CONSTRAINT topic_cluster_memberships_cluster_id_fkey
        FOREIGN KEY (cluster_id) REFERENCES %I.topic_clusters(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
END;
$$ LANGUAGE plpgsql;

-- Finance-specific foreign keys
ALTER TABLE finance.corporate_announcements
DROP CONSTRAINT IF EXISTS corporate_announcements_article_id_fkey;

ALTER TABLE finance.corporate_announcements
ADD CONSTRAINT corporate_announcements_article_id_fkey
FOREIGN KEY (article_id) REFERENCES finance.articles(id) ON DELETE SET NULL;

-- ============================================================================
-- INDEXES FOR DOMAIN SCHEMAS
-- ============================================================================

-- Function to create indexes for a domain schema
CREATE OR REPLACE FUNCTION create_domain_indexes(schema_name TEXT)
RETURNS VOID AS $$
DECLARE
    col_exists BOOLEAN;
BEGIN
    -- Articles indexes (check if columns exist first)
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%I_articles_published_at ON %I.articles(published_at DESC);
    ', schema_name, schema_name);
    
    -- Check and create source_domain index if column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = schema_name 
        AND table_name = 'articles' 
        AND column_name = 'source_domain'
    ) INTO col_exists;
    IF col_exists THEN
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_articles_source_domain ON %I.articles(source_domain);', schema_name, schema_name);
    END IF;
    
    -- Check and create processing_status index if column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = schema_name 
        AND table_name = 'articles' 
        AND column_name = 'processing_status'
    ) INTO col_exists;
    IF col_exists THEN
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_articles_processing_status ON %I.articles(processing_status);', schema_name, schema_name);
    END IF;
    
    -- Check and create url index if column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = schema_name 
        AND table_name = 'articles' 
        AND column_name = 'url'
    ) INTO col_exists;
    IF col_exists THEN
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_articles_url ON %I.articles(url);', schema_name, schema_name);
    END IF;
    
    -- Topics indexes (only if table exists)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = schema_name AND table_name = 'topics') THEN
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%I_topics_name ON %I.topics(name);
            CREATE INDEX IF NOT EXISTS idx_%I_topics_status ON %I.topics(status);
        ', schema_name, schema_name, schema_name, schema_name);
        
        -- Check for category column
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = schema_name AND table_name = 'topics' AND column_name = 'category'
        ) INTO col_exists;
        IF col_exists THEN
            EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_topics_category ON %I.topics(category);', schema_name, schema_name);
        END IF;
        
        -- Check for confidence_score column
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = schema_name AND table_name = 'topics' AND column_name = 'confidence_score'
        ) INTO col_exists;
        IF col_exists THEN
            EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_topics_confidence ON %I.topics(confidence_score DESC);', schema_name, schema_name);
        END IF;
        
        -- Check for keywords column (array)
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = schema_name AND table_name = 'topics' AND column_name = 'keywords'
        ) INTO col_exists;
        IF col_exists THEN
            EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_topics_keywords ON %I.topics USING GIN(keywords);', schema_name, schema_name);
        END IF;
    END IF;
    
    -- Article-Topic Assignments indexes (only if table exists)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = schema_name AND table_name = 'article_topic_assignments') THEN
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%I_ata_article ON %I.article_topic_assignments(article_id);
            CREATE INDEX IF NOT EXISTS idx_%I_ata_topic ON %I.article_topic_assignments(topic_id);
        ', schema_name, schema_name, schema_name, schema_name);
        
        -- Check for confidence_score column
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = schema_name AND table_name = 'article_topic_assignments' AND column_name = 'confidence_score'
        ) INTO col_exists;
        IF col_exists THEN
            EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_ata_confidence ON %I.article_topic_assignments(confidence_score DESC);', schema_name, schema_name);
        END IF;
    END IF;
    
    -- Storylines indexes
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%I_storylines_status ON %I.storylines(status);
        CREATE INDEX IF NOT EXISTS idx_%I_storylines_created_at ON %I.storylines(created_at DESC);
    ', schema_name, schema_name, schema_name, schema_name);
    
    -- RSS Feeds indexes (only if table exists)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = schema_name AND table_name = 'rss_feeds') THEN
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_feeds_active ON %I.rss_feeds(is_active);', schema_name, schema_name);
        
        -- Check for url or feed_url column
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = schema_name AND table_name = 'rss_feeds' 
            AND column_name IN ('url', 'feed_url')
        ) INTO col_exists;
        IF col_exists THEN
            -- Try url first, then feed_url
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = schema_name AND table_name = 'rss_feeds' AND column_name = 'url'
            ) INTO col_exists;
            IF col_exists THEN
                EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_feeds_url ON %I.rss_feeds(url);', schema_name, schema_name);
            ELSE
                EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_feeds_url ON %I.rss_feeds(feed_url);', schema_name, schema_name);
            END IF;
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create indexes for all domains
SELECT create_domain_indexes('politics');
SELECT create_domain_indexes('finance');
SELECT create_domain_indexes('science_tech');

-- Finance-specific indexes
CREATE INDEX IF NOT EXISTS idx_finance_market_patterns_type ON finance.market_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_finance_market_patterns_detected_at ON finance.market_patterns(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_finance_market_patterns_confidence ON finance.market_patterns(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_finance_market_patterns_companies ON finance.market_patterns USING GIN(affected_companies);

CREATE INDEX IF NOT EXISTS idx_finance_corporate_announcements_company ON finance.corporate_announcements(company_name);
CREATE INDEX IF NOT EXISTS idx_finance_corporate_announcements_ticker ON finance.corporate_announcements(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_finance_corporate_announcements_type ON finance.corporate_announcements(announcement_type);
CREATE INDEX IF NOT EXISTS idx_finance_corporate_announcements_date ON finance.corporate_announcements(announcement_date DESC);
CREATE INDEX IF NOT EXISTS idx_finance_corporate_announcements_sentiment ON finance.corporate_announcements(sentiment_score);

CREATE INDEX IF NOT EXISTS idx_finance_financial_indicators_company ON finance.financial_indicators(company_name);
CREATE INDEX IF NOT EXISTS idx_finance_financial_indicators_ticker ON finance.financial_indicators(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_finance_financial_indicators_type ON finance.financial_indicators(indicator_type);
CREATE INDEX IF NOT EXISTS idx_finance_financial_indicators_period ON finance.financial_indicators(period_start, period_end);

-- ============================================================================
-- TRIGGERS FOR DOMAIN SCHEMAS
-- ============================================================================

-- Create updated_at trigger function (in public schema, shared by all)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to create updated_at triggers for a domain schema
CREATE OR REPLACE FUNCTION create_domain_triggers(schema_name TEXT)
RETURNS VOID AS $$
BEGIN
    -- Add triggers to tables
    EXECUTE format('
        DROP TRIGGER IF EXISTS update_%I_articles_updated_at ON %I.articles;
        CREATE TRIGGER update_%I_articles_updated_at
        BEFORE UPDATE ON %I.articles
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        
        DROP TRIGGER IF EXISTS update_%I_topics_updated_at ON %I.topics;
        CREATE TRIGGER update_%I_topics_updated_at
        BEFORE UPDATE ON %I.topics
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        
        DROP TRIGGER IF EXISTS update_%I_storylines_updated_at ON %I.storylines;
        CREATE TRIGGER update_%I_storylines_updated_at
        BEFORE UPDATE ON %I.storylines
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    ', schema_name, schema_name, schema_name, schema_name, 
       schema_name, schema_name, schema_name, schema_name,
       schema_name, schema_name, schema_name, schema_name);
END;
$$ LANGUAGE plpgsql;

-- Create triggers for all domains
SELECT create_domain_triggers('politics');
SELECT create_domain_triggers('finance');
SELECT create_domain_triggers('science_tech');

-- Finance-specific triggers
DROP TRIGGER IF EXISTS update_finance_market_patterns_updated_at ON finance.market_patterns;
CREATE TRIGGER update_finance_market_patterns_updated_at
BEFORE UPDATE ON finance.market_patterns
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_finance_corporate_announcements_updated_at ON finance.corporate_announcements;
CREATE TRIGGER update_finance_corporate_announcements_updated_at
BEFORE UPDATE ON finance.corporate_announcements
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_finance_financial_indicators_updated_at ON finance.financial_indicators;
CREATE TRIGGER update_finance_financial_indicators_updated_at
BEFORE UPDATE ON finance.financial_indicators
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SEQUENCE MANAGEMENT
-- ============================================================================

-- Note: Sequences are automatically created with SERIAL columns
-- We'll preserve existing ID ranges during migration
-- Politics: Keep existing IDs
-- Finance: Start from 1 (new domain)
-- Science-Tech: Start from 1 (new domain)

-- ============================================================================
-- COMMENTS AND DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE domains IS 'Configuration table for domain silos. Each domain has its own schema for data isolation.';
COMMENT ON TABLE domain_metadata IS 'Tracks statistics and metadata for each domain.';
COMMENT ON TABLE finance.market_patterns IS 'Detected market patterns from financial news and corporate announcements.';
COMMENT ON TABLE finance.corporate_announcements IS 'Corporate financial announcements from SEC filings, press releases, and news.';
COMMENT ON TABLE finance.financial_indicators IS 'Financial metrics and indicators for companies (revenue, profit, market cap, etc.).';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 122: Domain Silo Infrastructure created successfully';
    RAISE NOTICE 'Created schemas: politics, finance, science_tech';
    RAISE NOTICE 'Created domains table with 3 default domains';
    RAISE NOTICE 'Created all domain-specific tables';
    RAISE NOTICE 'Created finance-specific tables: market_patterns, corporate_announcements, financial_indicators';
    RAISE NOTICE 'Next step: Data migration (Migration 123)';
END $$;

