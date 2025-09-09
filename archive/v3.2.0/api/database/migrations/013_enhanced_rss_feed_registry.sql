-- Migration 013: Enhanced RSS Feed Registry System
-- Creates comprehensive feed management with tiers, categories, and filtering

-- Enhanced RSS Feeds table with comprehensive management features
CREATE TABLE IF NOT EXISTS rss_feeds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL UNIQUE,
    description TEXT,
    tier INTEGER NOT NULL DEFAULT 2 CHECK (tier IN (1, 2, 3)), -- 1=wire services, 2=institutions, 3=specialized
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10), -- 1=highest, 10=lowest
    language VARCHAR(10) DEFAULT 'en',
    country VARCHAR(100),
    category VARCHAR(50) NOT NULL, -- politics, economy, tech, climate, world, business
    subcategory VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'active', -- active, inactive, error, warning, maintenance
    update_frequency INTEGER DEFAULT 30, -- minutes between updates
    max_articles_per_update INTEGER DEFAULT 50,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    avg_response_time INTEGER DEFAULT 0,
    reliability_score DECIMAL(3,2) DEFAULT 0.0,
    last_fetched TIMESTAMP WITH TIME ZONE,
    last_success TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    warning_message TEXT,
    tags JSONB DEFAULT '[]', -- Array of tags for categorization
    custom_headers JSONB DEFAULT '{}', -- Custom HTTP headers
    filters JSONB DEFAULT '{}', -- Content filtering rules
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Feed Categories table for better organization
CREATE TABLE IF NOT EXISTS feed_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    parent_category VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default categories
INSERT INTO feed_categories (name, description, parent_category) VALUES
('politics', 'Political news and analysis', NULL),
('economy', 'Economic news and financial markets', NULL),
('technology', 'Technology news and innovation', NULL),
('climate', 'Climate change and environmental news', NULL),
('world', 'International news and global events', NULL),
('business', 'Business news and corporate updates', NULL),
('health', 'Health and medical news', NULL),
('science', 'Scientific research and discoveries', NULL),
('security', 'Cybersecurity and national security', NULL),
('energy', 'Energy sector and renewable resources', NULL)
ON CONFLICT (name) DO NOTHING;

-- Feed Filtering Rules table
CREATE TABLE IF NOT EXISTS feed_filtering_rules (
    id SERIAL PRIMARY KEY,
    feed_id INTEGER REFERENCES rss_feeds(id) ON DELETE CASCADE,
    rule_type VARCHAR(50) NOT NULL, -- keyword_blacklist, category_filter, nlp_classifier, url_pattern
    rule_config JSONB NOT NULL, -- Configuration for the rule
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Global Filtering Configuration table
CREATE TABLE IF NOT EXISTS global_filtering_config (
    id SERIAL PRIMARY KEY,
    config_name VARCHAR(100) NOT NULL UNIQUE,
    config_data JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default global filtering configuration
INSERT INTO global_filtering_config (config_name, config_data) VALUES
('keyword_blacklist', '{
    "entertainment": ["celebrity", "oscars", "grammy", "emmy", "hollywood", "movie", "film", "actor", "actress", "singer", "musician"],
    "sports": ["nfl", "nba", "mlb", "nhl", "soccer", "football", "basketball", "baseball", "hockey", "olympics", "world cup"],
    "lifestyle": ["fashion", "beauty", "makeup", "tiktok", "instagram", "social media", "influencer", "trending", "viral"],
    "gossip": ["rumor", "scandal", "divorce", "marriage", "dating", "relationship", "breakup"]
}'),
('category_whitelist', '{
    "politics": ["election", "government", "policy", "legislation", "congress", "senate", "parliament", "democracy", "voting"],
    "economy": ["market", "economy", "financial", "business", "trade", "inflation", "gdp", "unemployment", "recession"],
    "technology": ["tech", "innovation", "ai", "artificial intelligence", "cybersecurity", "digital", "software", "hardware"],
    "climate": ["climate", "environment", "carbon", "renewable", "sustainability", "green", "emissions", "global warming"],
    "world": ["international", "global", "world", "foreign", "diplomacy", "conflict", "peace", "treaty", "summit"]
}'),
('nlp_classifier_config', '{
    "model_name": "facebook/bart-large-mnli",
    "categories": ["politics", "economy", "technology", "climate", "world", "business"],
    "threshold": 0.7,
    "exclude_categories": ["entertainment", "sports", "lifestyle", "gossip"]
}'),
('url_patterns', '{
    "include_patterns": ["/politics/", "/economy/", "/tech/", "/business/", "/world/", "/climate/", "/environment/"],
    "exclude_patterns": ["/sports/", "/entertainment/", "/lifestyle/", "/gossip/", "/celebrity/", "/fashion/"]
}')
ON CONFLICT (config_name) DO NOTHING;

-- Feed Performance Metrics table
CREATE TABLE IF NOT EXISTS feed_performance_metrics (
    id SERIAL PRIMARY KEY,
    feed_id INTEGER NOT NULL REFERENCES rss_feeds(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    articles_fetched INTEGER DEFAULT 0,
    articles_filtered_out INTEGER DEFAULT 0,
    articles_accepted INTEGER DEFAULT 0,
    duplicates_found INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    avg_response_time INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_check TIMESTAMP WITH TIME ZONE,
    last_success TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(feed_id, date)
);

-- Enhanced Articles table with metadata enrichment
ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_tier INTEGER DEFAULT 2;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_priority INTEGER DEFAULT 5;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS detected_language VARCHAR(10);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_translated BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS categories JSONB DEFAULT '[]';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS geography JSONB DEFAULT '[]';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS entities JSONB DEFAULT '[]';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS sentiment_score DECIMAL(3,2);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS quality_score DECIMAL(3,2);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS cluster_id INTEGER;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS canonical_article_id INTEGER REFERENCES articles(id);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS filtering_reason TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS enrichment_status VARCHAR(20) DEFAULT 'pending';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_rss_feeds_tier ON rss_feeds(tier);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_priority ON rss_feeds(priority);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_category ON rss_feeds(category);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_status ON rss_feeds(status);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_is_active ON rss_feeds(is_active);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_language ON rss_feeds(language);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_country ON rss_feeds(country);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_reliability_score ON rss_feeds(reliability_score);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_last_fetched ON rss_feeds(last_fetched);

CREATE INDEX IF NOT EXISTS idx_feed_filtering_rules_feed_id ON feed_filtering_rules(feed_id);
CREATE INDEX IF NOT EXISTS idx_feed_filtering_rules_type ON feed_filtering_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_feed_filtering_rules_active ON feed_filtering_rules(is_active);

CREATE INDEX IF NOT EXISTS idx_articles_source_tier ON articles(source_tier);
CREATE INDEX IF NOT EXISTS idx_articles_language ON articles(language);
CREATE INDEX IF NOT EXISTS idx_articles_categories ON articles USING GIN(categories);
CREATE INDEX IF NOT EXISTS idx_articles_geography ON articles USING GIN(geography);
CREATE INDEX IF NOT EXISTS idx_articles_entities ON articles USING GIN(entities);
CREATE INDEX IF NOT EXISTS idx_articles_is_duplicate ON articles(is_duplicate);
CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_canonical ON articles(canonical_article_id);
CREATE INDEX IF NOT EXISTS idx_articles_enrichment_status ON articles(enrichment_status);

CREATE INDEX IF NOT EXISTS idx_feed_performance_metrics_feed_date ON feed_performance_metrics(feed_id, date);
CREATE INDEX IF NOT EXISTS idx_feed_performance_metrics_date ON feed_performance_metrics(date);

-- Create triggers for updated_at timestamps
DROP TRIGGER IF EXISTS update_rss_feeds_updated_at ON rss_feeds;
CREATE TRIGGER update_rss_feeds_updated_at
    BEFORE UPDATE ON rss_feeds
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_feed_filtering_rules_updated_at ON feed_filtering_rules;
CREATE TRIGGER update_feed_filtering_rules_updated_at
    BEFORE UPDATE ON feed_filtering_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_global_filtering_config_updated_at ON global_filtering_config;
CREATE TRIGGER update_global_filtering_config_updated_at
    BEFORE UPDATE ON global_filtering_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE rss_feeds IS 'Enhanced RSS feed registry with tier system and comprehensive management';
COMMENT ON TABLE feed_categories IS 'Categories for organizing RSS feeds';
COMMENT ON TABLE feed_filtering_rules IS 'Individual filtering rules for specific feeds';
COMMENT ON TABLE global_filtering_config IS 'Global filtering configuration for all feeds';
COMMENT ON TABLE feed_performance_metrics IS 'Daily performance metrics for RSS feeds';

COMMENT ON COLUMN rss_feeds.tier IS 'Feed tier: 1=wire services (Reuters, AP), 2=institutions (BBC, CNN), 3=specialized (TechCrunch, Ars)';
COMMENT ON COLUMN rss_feeds.priority IS 'Processing priority: 1=highest, 10=lowest';
COMMENT ON COLUMN rss_feeds.reliability_score IS 'Overall reliability score (0.0-1.0) based on accuracy and consistency';
COMMENT ON COLUMN rss_feeds.tags IS 'JSON array of tags for categorization and filtering';
COMMENT ON COLUMN rss_feeds.custom_headers IS 'JSON object of custom HTTP headers for requests';
COMMENT ON COLUMN rss_feeds.filters IS 'JSON object of content filtering rules';

COMMENT ON COLUMN articles.source_tier IS 'Tier of the source that provided this article';
COMMENT ON COLUMN articles.categories IS 'JSON array of detected categories';
COMMENT ON COLUMN articles.geography IS 'JSON array of detected geographical entities';
COMMENT ON COLUMN articles.entities IS 'JSON array of detected named entities';
COMMENT ON COLUMN articles.cluster_id IS 'ID of the duplicate cluster this article belongs to';
COMMENT ON COLUMN articles.canonical_article_id IS 'ID of the canonical article if this is a duplicate';
COMMENT ON COLUMN articles.filtering_reason IS 'Reason why article was filtered out (if applicable)';
COMMENT ON COLUMN articles.enrichment_status IS 'Status of metadata enrichment: pending, completed, failed';

