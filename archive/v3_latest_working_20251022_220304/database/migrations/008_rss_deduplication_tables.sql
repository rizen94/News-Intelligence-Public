-- Migration 008: RSS Management and Deduplication Tables
-- Creates tables for RSS feed management and duplicate detection

-- Enhanced RSS Feeds table with additional fields
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en';
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS update_frequency INTEGER DEFAULT 30;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS max_articles_per_update INTEGER DEFAULT 50;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS success_rate DECIMAL(5,2) DEFAULT 0.0;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS avg_response_time INTEGER DEFAULT 0;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS warning_message TEXT;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]';
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS custom_headers JSONB DEFAULT '{}';
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS filters JSONB DEFAULT '{}';
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Update existing records to have updated_at timestamp
UPDATE rss_feeds SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;

-- Duplicate Pairs table
CREATE TABLE IF NOT EXISTS duplicate_pairs (
    id SERIAL PRIMARY KEY,
    article1_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    article2_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    similarity_score DECIMAL(4,3) NOT NULL,
    title_similarity DECIMAL(4,3) DEFAULT 0.0,
    content_similarity DECIMAL(4,3) DEFAULT 0.0,
    algorithm VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article1_id, article2_id)
);

-- Deduplication Settings table
CREATE TABLE IF NOT EXISTS deduplication_settings (
    id SERIAL PRIMARY KEY,
    similarity_threshold DECIMAL(4,3) DEFAULT 0.85,
    auto_remove BOOLEAN DEFAULT FALSE,
    min_article_length INTEGER DEFAULT 100,
    max_articles_to_process INTEGER DEFAULT 1000,
    enabled_algorithms JSONB DEFAULT '["content_similarity", "title_similarity", "url_similarity"]',
    exclude_sources JSONB DEFAULT '[]',
    include_sources JSONB DEFAULT '[]',
    time_window_hours INTEGER DEFAULT 24,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default deduplication settings
INSERT INTO deduplication_settings (
    similarity_threshold, auto_remove, min_article_length,
    max_articles_to_process, enabled_algorithms, exclude_sources,
    include_sources, time_window_hours
) VALUES (
    0.85, FALSE, 100, 1000,
    '["content_similarity", "title_similarity", "url_similarity"]',
    '[]', '[]', 24
) ON CONFLICT DO NOTHING;

-- Deduplication Statistics table
CREATE TABLE IF NOT EXISTS deduplication_stats (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    total_duplicates INTEGER DEFAULT 0,
    pending_review INTEGER DEFAULT 0,
    high_similarity INTEGER DEFAULT 0,
    very_high_similarity INTEGER DEFAULT 0,
    medium_similarity INTEGER DEFAULT 0,
    low_similarity INTEGER DEFAULT 0,
    removed_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    accuracy_rate DECIMAL(5,2) DEFAULT 0.0,
    processing_time FLOAT DEFAULT 0.0,
    articles_processed INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date)
);

-- RSS Feed Statistics table
CREATE TABLE IF NOT EXISTS rss_feed_stats (
    id SERIAL PRIMARY KEY,
    feed_id INTEGER NOT NULL REFERENCES rss_feeds(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    articles_collected INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    avg_response_time INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_check TIMESTAMP WITH TIME ZONE,
    last_success TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(feed_id, date)
);

-- RSS Collection Log table
CREATE TABLE IF NOT EXISTS rss_collection_log (
    id SERIAL PRIMARY KEY,
    feed_id INTEGER NOT NULL REFERENCES rss_feeds(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'running',
    articles_found INTEGER DEFAULT 0,
    articles_added INTEGER DEFAULT 0,
    articles_duplicates INTEGER DEFAULT 0,
    response_time INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_rss_feeds_status ON rss_feeds(status);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_category ON rss_feeds(category);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_is_active ON rss_feeds(is_active);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_updated_at ON rss_feeds(updated_at);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_success_rate ON rss_feeds(success_rate);

CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_article1 ON duplicate_pairs(article1_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_article2 ON duplicate_pairs(article2_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_similarity ON duplicate_pairs(similarity_score);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_status ON duplicate_pairs(status);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_algorithm ON duplicate_pairs(algorithm);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_detected_at ON duplicate_pairs(detected_at);

CREATE INDEX IF NOT EXISTS idx_deduplication_stats_date ON deduplication_stats(date);
CREATE INDEX IF NOT EXISTS idx_rss_feed_stats_feed_date ON rss_feed_stats(feed_id, date);
CREATE INDEX IF NOT EXISTS idx_rss_collection_log_feed ON rss_collection_log(feed_id);
CREATE INDEX IF NOT EXISTS idx_rss_collection_log_started_at ON rss_collection_log(started_at);

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables
DROP TRIGGER IF EXISTS update_rss_feeds_updated_at ON rss_feeds;
CREATE TRIGGER update_rss_feeds_updated_at
    BEFORE UPDATE ON rss_feeds
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_duplicate_pairs_updated_at ON duplicate_pairs;
CREATE TRIGGER update_duplicate_pairs_updated_at
    BEFORE UPDATE ON duplicate_pairs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_deduplication_settings_updated_at ON deduplication_settings;
CREATE TRIGGER update_deduplication_settings_updated_at
    BEFORE UPDATE ON deduplication_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE duplicate_pairs IS 'Stores detected duplicate article pairs with similarity scores';
COMMENT ON TABLE deduplication_settings IS 'Stores configuration for duplicate detection algorithms';
COMMENT ON TABLE deduplication_stats IS 'Daily statistics for deduplication performance';
COMMENT ON TABLE rss_feed_stats IS 'Daily statistics for RSS feed performance';
COMMENT ON TABLE rss_collection_log IS 'Log of RSS collection attempts and results';

COMMENT ON COLUMN duplicate_pairs.similarity_score IS 'Overall similarity score (0.0-1.0)';
COMMENT ON COLUMN duplicate_pairs.algorithm IS 'Detection algorithm used: content_similarity, title_similarity, url_similarity';
COMMENT ON COLUMN duplicate_pairs.status IS 'Status: pending, confirmed, rejected, removed';

COMMENT ON COLUMN deduplication_settings.similarity_threshold IS 'Minimum similarity score to consider articles as duplicates';
COMMENT ON COLUMN deduplication_settings.enabled_algorithms IS 'JSON array of enabled detection algorithms';

COMMENT ON COLUMN rss_feeds.status IS 'Current status: active, inactive, error, warning';
COMMENT ON COLUMN rss_feeds.success_rate IS 'Percentage of successful collection attempts';
COMMENT ON COLUMN rss_feeds.avg_response_time IS 'Average response time in milliseconds';
COMMENT ON COLUMN rss_feeds.tags IS 'JSON array of feed tags for categorization';
COMMENT ON COLUMN rss_feeds.custom_headers IS 'JSON object of custom HTTP headers';
COMMENT ON COLUMN rss_feeds.filters IS 'JSON object of content filtering rules';
