-- News Intelligence System v3.3.0 - Database Schema Alignment Migration
-- This migration aligns the database schema with the API documentation and service requirements
-- Date: 2025-09-26
-- Version: 3.3.0

-- ============================================================================
-- RSS FEEDS TABLE ALIGNMENT
-- ============================================================================

-- Add missing columns to rss_feeds table
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS max_articles INTEGER DEFAULT 50;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS update_frequency INTEGER DEFAULT 30;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 1;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS country VARCHAR(50);
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS category VARCHAR(100);
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100);
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS tier INTEGER DEFAULT 1;

-- Add comments for documentation
COMMENT ON COLUMN rss_feeds.max_articles IS 'Maximum articles to fetch per update cycle';
COMMENT ON COLUMN rss_feeds.update_frequency IS 'Update frequency in minutes';
COMMENT ON COLUMN rss_feeds.priority IS 'Feed priority (1-10, higher is more important)';
COMMENT ON COLUMN rss_feeds.country IS 'Country code for the feed';
COMMENT ON COLUMN rss_feeds.category IS 'Feed category (news, sports, politics, etc.)';
COMMENT ON COLUMN rss_feeds.subcategory IS 'Feed subcategory for more specific classification';
COMMENT ON COLUMN rss_feeds.tier IS 'Feed tier (1-5, higher tier gets more resources)';

-- ============================================================================
-- ARTICLES TABLE ALIGNMENT
-- ============================================================================

-- Add missing columns to articles table
ALTER TABLE articles ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) DEFAULT 'raw';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS author VARCHAR(255);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS category VARCHAR(100);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS country VARCHAR(50);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS word_count INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS reading_time INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS deduplication_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS similarity_score NUMERIC(4,3);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS cluster_id INTEGER;

-- Add comments for documentation
COMMENT ON COLUMN articles.processing_status IS 'Article processing status (raw, processing, processed, failed)';
COMMENT ON COLUMN articles.author IS 'Article author name';
COMMENT ON COLUMN articles.category IS 'Article category (news, sports, politics, etc.)';
COMMENT ON COLUMN articles.subcategory IS 'Article subcategory for more specific classification';
COMMENT ON COLUMN articles.country IS 'Country code for the article';
COMMENT ON COLUMN articles.language IS 'Article language code (ISO 639-1)';
COMMENT ON COLUMN articles.word_count IS 'Number of words in the article';
COMMENT ON COLUMN articles.reading_time IS 'Estimated reading time in minutes';
COMMENT ON COLUMN articles.content_hash IS 'SHA256 hash of normalized content for deduplication';
COMMENT ON COLUMN articles.deduplication_status IS 'Deduplication processing status';
COMMENT ON COLUMN articles.similarity_score IS 'Similarity score with other articles (0-1)';
COMMENT ON COLUMN articles.cluster_id IS 'ID of the article cluster for storyline suggestions';

-- ============================================================================
-- STORYLINES TABLE ALIGNMENT
-- ============================================================================

-- Add missing columns to storylines table
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS category VARCHAR(100);
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100);
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS tags TEXT[];
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 1;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS key_entities JSONB;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS sentiment_trend JSONB;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS source_diversity JSONB;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS last_article_added TIMESTAMP;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS article_count INTEGER DEFAULT 0;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_processed BOOLEAN DEFAULT FALSE;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_processing_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS rag_content JSONB;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Add comments for documentation
COMMENT ON COLUMN storylines.category IS 'Storyline category (politics, sports, technology, etc.)';
COMMENT ON COLUMN storylines.subcategory IS 'Storyline subcategory for more specific classification';
COMMENT ON COLUMN storylines.tags IS 'Array of tags for storyline classification';
COMMENT ON COLUMN storylines.priority IS 'Storyline priority (1-10, higher is more important)';
COMMENT ON COLUMN storylines.key_entities IS 'Key entities extracted from storyline articles';
COMMENT ON COLUMN storylines.sentiment_trend IS 'Sentiment trend analysis over time';
COMMENT ON COLUMN storylines.source_diversity IS 'Source diversity metrics for the storyline';
COMMENT ON COLUMN storylines.last_article_added IS 'Timestamp of last article added to storyline';
COMMENT ON COLUMN storylines.article_count IS 'Number of articles in the storyline';
COMMENT ON COLUMN storylines.ml_processed IS 'Whether storyline has been processed by ML';
COMMENT ON COLUMN storylines.ml_processing_status IS 'ML processing status (pending, processing, completed, failed)';
COMMENT ON COLUMN storylines.rag_content IS 'RAG (Retrieval-Augmented Generation) content';
COMMENT ON COLUMN storylines.metadata IS 'Additional metadata for the storyline';

-- ============================================================================
-- STORYLINE_ARTICLES TABLE ALIGNMENT
-- ============================================================================

-- Add missing columns to storyline_articles table
ALTER TABLE storyline_articles ADD COLUMN IF NOT EXISTS added_by VARCHAR(255);
ALTER TABLE storyline_articles ADD COLUMN IF NOT EXISTS temporal_order INTEGER;
ALTER TABLE storyline_articles ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE storyline_articles ADD COLUMN IF NOT EXISTS ml_analysis JSONB;

-- Add comments for documentation
COMMENT ON COLUMN storyline_articles.added_by IS 'User who added the article to the storyline';
COMMENT ON COLUMN storyline_articles.temporal_order IS 'Temporal order of articles in the storyline';
COMMENT ON COLUMN storyline_articles.notes IS 'Additional notes about the article in this storyline';
COMMENT ON COLUMN storyline_articles.ml_analysis IS 'ML analysis data for the article-storyline relationship';

-- ============================================================================
-- PERFORMANCE INDEXES
-- ============================================================================

-- Create indexes for improved query performance
CREATE INDEX IF NOT EXISTS idx_articles_processing_status ON articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_country ON articles(country);
CREATE INDEX IF NOT EXISTS idx_articles_language ON articles(language);
CREATE INDEX IF NOT EXISTS idx_articles_quality_score ON articles(quality_score);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);

CREATE INDEX IF NOT EXISTS idx_rss_feeds_status ON rss_feeds(is_active);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_priority ON rss_feeds(priority);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_tier ON rss_feeds(tier);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_category ON rss_feeds(category);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_country ON rss_feeds(country);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_last_fetched ON rss_feeds(last_fetched);

CREATE INDEX IF NOT EXISTS idx_storylines_status ON storylines(status);
CREATE INDEX IF NOT EXISTS idx_storylines_category ON storylines(category);
CREATE INDEX IF NOT EXISTS idx_storylines_priority ON storylines(priority);
CREATE INDEX IF NOT EXISTS idx_storylines_ml_processed ON storylines(ml_processed);
CREATE INDEX IF NOT EXISTS idx_storylines_article_count ON storylines(article_count);
CREATE INDEX IF NOT EXISTS idx_storylines_updated_at ON storylines(updated_at);

CREATE INDEX IF NOT EXISTS idx_storyline_articles_storyline_id ON storyline_articles(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_article_id ON storyline_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_relevance_score ON storyline_articles(relevance_score);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_importance_score ON storyline_articles(importance_score);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_temporal_order ON storyline_articles(temporal_order);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_added_at ON storyline_articles(added_at);

-- ============================================================================
-- CONSTRAINTS AND VALIDATIONS
-- ============================================================================

-- Add check constraints for data validation
ALTER TABLE rss_feeds ADD CONSTRAINT IF NOT EXISTS chk_rss_feeds_tier CHECK (tier >= 1 AND tier <= 5);
ALTER TABLE rss_feeds ADD CONSTRAINT IF NOT EXISTS chk_rss_feeds_priority CHECK (priority >= 1 AND priority <= 10);
ALTER TABLE rss_feeds ADD CONSTRAINT IF NOT EXISTS chk_rss_feeds_max_articles CHECK (max_articles > 0);
ALTER TABLE rss_feeds ADD CONSTRAINT IF NOT EXISTS chk_rss_feeds_update_frequency CHECK (update_frequency > 0);

ALTER TABLE articles ADD CONSTRAINT IF NOT EXISTS chk_articles_quality_score CHECK (quality_score >= 0 AND quality_score <= 1);
ALTER TABLE articles ADD CONSTRAINT IF NOT EXISTS chk_articles_sentiment_score CHECK (sentiment_score >= -1 AND sentiment_score <= 1);
ALTER TABLE articles ADD CONSTRAINT IF NOT EXISTS chk_articles_readability_score CHECK (readability_score >= 0 AND readability_score <= 1);
ALTER TABLE articles ADD CONSTRAINT IF NOT EXISTS chk_articles_similarity_score CHECK (similarity_score >= 0 AND similarity_score <= 1);
ALTER TABLE articles ADD CONSTRAINT IF NOT EXISTS chk_articles_word_count CHECK (word_count >= 0);
ALTER TABLE articles ADD CONSTRAINT IF NOT EXISTS chk_articles_reading_time CHECK (reading_time >= 0);

ALTER TABLE storylines ADD CONSTRAINT IF NOT EXISTS chk_storylines_priority CHECK (priority >= 1 AND priority <= 10);
ALTER TABLE storylines ADD CONSTRAINT IF NOT EXISTS chk_storylines_article_count CHECK (article_count >= 0);

ALTER TABLE storyline_articles ADD CONSTRAINT IF NOT EXISTS chk_storyline_articles_relevance_score CHECK (relevance_score >= 0 AND relevance_score <= 1);
ALTER TABLE storyline_articles ADD CONSTRAINT IF NOT EXISTS chk_storyline_articles_importance_score CHECK (importance_score >= 0 AND importance_score <= 1);
ALTER TABLE storyline_articles ADD CONSTRAINT IF NOT EXISTS chk_storyline_articles_temporal_order CHECK (temporal_order >= 0);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Create views for common query patterns
CREATE OR REPLACE VIEW article_summary AS
SELECT 
    id,
    title,
    source,
    author,
    category,
    country,
    language,
    status,
    processing_status,
    quality_score,
    sentiment_score,
    word_count,
    reading_time,
    published_at,
    created_at,
    updated_at
FROM articles;

CREATE OR REPLACE VIEW storyline_summary AS
SELECT 
    id,
    title,
    description,
    status,
    category,
    priority,
    article_count,
    ml_processed,
    ml_processing_status,
    last_article_added,
    created_at,
    updated_at
FROM storylines;

CREATE OR REPLACE VIEW rss_feed_summary AS
SELECT 
    id,
    name,
    url,
    category,
    subcategory,
    country,
    tier,
    priority,
    is_active,
    max_articles,
    update_frequency,
    last_fetched,
    created_at
FROM rss_feeds;

-- ============================================================================
-- FUNCTIONS FOR COMMON OPERATIONS
-- ============================================================================

-- Function to update article count in storylines
CREATE OR REPLACE FUNCTION update_storyline_article_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE storylines 
        SET article_count = article_count + 1,
            last_article_added = CURRENT_TIMESTAMP
        WHERE id = NEW.storyline_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE storylines 
        SET article_count = GREATEST(article_count - 1, 0)
        WHERE id = OLD.storyline_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic article count updates
DROP TRIGGER IF EXISTS trigger_update_storyline_article_count ON storyline_articles;
CREATE TRIGGER trigger_update_storyline_article_count
    AFTER INSERT OR DELETE ON storyline_articles
    FOR EACH ROW EXECUTE FUNCTION update_storyline_article_count();

-- Function to generate content hash for articles
CREATE OR REPLACE FUNCTION generate_article_content_hash()
RETURNS TRIGGER AS $$
BEGIN
    -- Generate hash from title and content
    NEW.content_hash := encode(digest(COALESCE(NEW.title, '') || '|' || COALESCE(NEW.content, ''), 'sha256'), 'hex');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic content hash generation
DROP TRIGGER IF EXISTS trigger_generate_content_hash ON articles;
CREATE TRIGGER trigger_generate_content_hash
    BEFORE INSERT OR UPDATE ON articles
    FOR EACH ROW EXECUTE FUNCTION generate_article_content_hash();

-- ============================================================================
-- DATA MIGRATION FOR EXISTING RECORDS
-- ============================================================================

-- Update existing articles with default values
UPDATE articles SET 
    processing_status = 'raw',
    language = 'en',
    word_count = COALESCE(array_length(string_to_array(content, ' '), 1), 0),
    reading_time = GREATEST(1, COALESCE(array_length(string_to_array(content, ' '), 1), 0) / 200),
    deduplication_status = 'pending'
WHERE processing_status IS NULL;

-- Update existing RSS feeds with default values
UPDATE rss_feeds SET 
    max_articles = 50,
    update_frequency = 30,
    priority = 1,
    tier = 1
WHERE max_articles IS NULL;

-- Update existing storylines with default values
UPDATE storylines SET 
    priority = 1,
    article_count = (
        SELECT COUNT(*) 
        FROM storyline_articles 
        WHERE storyline_id = storylines.id
    ),
    ml_processed = FALSE,
    ml_processing_status = 'pending'
WHERE priority IS NULL;

-- ============================================================================
-- GRANTS AND PERMISSIONS
-- ============================================================================

-- Grant necessary permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO newsapp;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO newsapp;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO newsapp;

-- ============================================================================
-- MIGRATION COMPLETION
-- ============================================================================

-- Log migration completion
INSERT INTO deduplication_log (operation, status, details, created_at)
VALUES (
    'schema_alignment_migration',
    'completed',
    'Database schema aligned with API documentation and service requirements',
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

-- Update system version
-- This would be in a system_metadata table if it exists
-- INSERT INTO system_metadata (key, value, updated_at) 
-- VALUES ('schema_version', '3.3.0', CURRENT_TIMESTAMP)
-- ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at;
