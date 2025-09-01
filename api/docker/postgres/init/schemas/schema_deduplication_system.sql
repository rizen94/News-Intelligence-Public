-- News Intelligence System v2.1.2 - Deduplication System Schema Updates
-- This script adds the necessary database schema for the deduplication system

-- ============================================================================
-- 1. ADD DEDUPLICATION COLUMNS TO ARTICLES TABLE
-- ============================================================================

-- Add duplicate tracking columns
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'duplicate_of'
    ) THEN
        ALTER TABLE articles ADD COLUMN duplicate_of INTEGER REFERENCES articles(id);
        RAISE NOTICE 'Added duplicate_of column to articles table';
    ELSE
        RAISE NOTICE 'duplicate_of column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'is_duplicate'
    ) THEN
        ALTER TABLE articles ADD COLUMN is_duplicate BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added is_duplicate column to articles table';
    ELSE
        RAISE NOTICE 'is_duplicate column already exists in articles table';
    END IF;
END $$;

-- Add URL normalization columns
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'canonical_url'
    ) THEN
        ALTER TABLE articles ADD COLUMN canonical_url VARCHAR(500);
        RAISE NOTICE 'Added canonical_url column to articles table';
    ELSE
        RAISE NOTICE 'canonical_url column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'url_hash'
    ) THEN
        ALTER TABLE articles ADD COLUMN url_hash VARCHAR(64);
        RAISE NOTICE 'Added url_hash column to articles table';
    ELSE
        RAISE NOTICE 'url_hash column already exists in articles table';
    END IF;
END $$;

-- Add content metrics columns
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'detected_language'
    ) THEN
        ALTER TABLE articles ADD COLUMN detected_language VARCHAR(10);
        RAISE NOTICE 'Added detected_language column to articles table';
    ELSE
        RAISE NOTICE 'detected_language column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'language_confidence'
    ) THEN
        ALTER TABLE articles ADD COLUMN language_confidence DECIMAL(5,2);
        RAISE NOTICE 'Added language_confidence column to articles table';
    ELSE
        RAISE NOTICE 'language_confidence column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'word_count'
    ) THEN
        ALTER TABLE articles ADD COLUMN word_count INTEGER;
        RAISE NOTICE 'Added word_count column to articles table';
    ELSE
        RAISE NOTICE 'word_count column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'sentence_count'
    ) THEN
        ALTER TABLE articles ADD COLUMN sentence_count INTEGER;
        RAISE NOTICE 'Added sentence_count column to articles table';
    ELSE
        RAISE NOTICE 'sentence_count column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'content_completeness_score'
    ) THEN
        ALTER TABLE articles ADD COLUMN content_completeness_score DECIMAL(5,2);
        RAISE NOTICE 'Added content_completeness_score column to articles table';
    ELSE
        RAISE NOTICE 'content_completeness_score column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'readability_score'
    ) THEN
        ALTER TABLE articles ADD COLUMN readability_score DECIMAL(5,2);
        RAISE NOTICE 'Added readability_score column to articles table';
    ELSE
        RAISE NOTICE 'readability_score column already exists in articles table';
    END IF;
END $$;

-- Add keyword extraction columns
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'extracted_keywords'
    ) THEN
        ALTER TABLE articles ADD COLUMN extracted_keywords TEXT[];
        RAISE NOTICE 'Added extracted_keywords column to articles table';
    ELSE
        RAISE NOTICE 'extracted_keywords column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'keyword_scores'
    ) THEN
        ALTER TABLE articles ADD COLUMN keyword_scores JSONB;
        RAISE NOTICE 'Added keyword_scores column to articles table';
    ELSE
        RAISE NOTICE 'keyword_scores column already exists in articles table';
    END IF;
END $$;

-- ============================================================================
-- 2. CREATE DEDUPLICATION TABLES
-- ============================================================================

-- Create duplicate groups table
CREATE TABLE IF NOT EXISTS duplicate_groups (
    group_id SERIAL PRIMARY KEY,
    original_article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    duplicate_count INTEGER DEFAULT 0,
    similarity_type VARCHAR(50), -- 'content_hash', 'url', 'semantic'
    avg_confidence_score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create feed health metrics table
CREATE TABLE IF NOT EXISTS feed_health_metrics (
    feed_id SERIAL PRIMARY KEY,
    feed_url VARCHAR(500) NOT NULL,
    feed_name VARCHAR(255),
    last_fetch_time TIMESTAMP,
    last_success_time TIMESTAMP,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    avg_response_time_ms INTEGER,
    error_count INTEGER DEFAULT 0,
    last_error_message TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create raw articles staging table
CREATE TABLE IF NOT EXISTS raw_articles_staging (
    staging_id SERIAL PRIMARY KEY,
    title TEXT,
    content TEXT,
    url VARCHAR(500),
    source VARCHAR(255),
    published_date TIMESTAMP,
    raw_data JSONB,
    quality_score DECIMAL(5,2),
    processing_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'quality_check', 'approved', 'rejected'
    quality_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create archived articles table
CREATE TABLE IF NOT EXISTS archived_articles (
    archive_id SERIAL PRIMARY KEY,
    original_article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    archived_at TIMESTAMP DEFAULT NOW(),
    archive_reason VARCHAR(100), -- 'age', 'low_quality', 'manual_archive'
    storage_location VARCHAR(255),
    archive_metadata JSONB
);

-- ============================================================================
-- 3. CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Articles table deduplication indexes
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_duplicate_of ON articles(duplicate_of);
CREATE INDEX IF NOT EXISTS idx_articles_is_duplicate ON articles(is_duplicate);
CREATE INDEX IF NOT EXISTS idx_articles_canonical_url ON articles(canonical_url);
CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash);

-- Articles table content metrics indexes
CREATE INDEX IF NOT EXISTS idx_articles_language ON articles(detected_language);
CREATE INDEX IF NOT EXISTS idx_articles_word_count ON articles(word_count);
CREATE INDEX IF NOT EXISTS idx_articles_quality_score ON articles(content_completeness_score);

-- Deduplication system indexes
CREATE INDEX IF NOT EXISTS idx_duplicate_groups_original ON duplicate_groups(original_article_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_groups_type ON duplicate_groups(similarity_type);
CREATE INDEX IF NOT EXISTS idx_duplicate_groups_created ON duplicate_groups(created_at);

-- Feed health indexes
CREATE INDEX IF NOT EXISTS idx_feed_health_url ON feed_health_metrics(feed_url);
CREATE INDEX IF NOT EXISTS idx_feed_health_active ON feed_health_metrics(is_active);
CREATE INDEX IF NOT EXISTS idx_feed_health_last_fetch ON feed_health_metrics(last_fetch_time);

-- Staging and archiving indexes
CREATE INDEX IF NOT EXISTS idx_staging_status ON raw_articles_staging(processing_status);
CREATE INDEX IF NOT EXISTS idx_staging_quality ON raw_articles_staging(quality_score);
CREATE INDEX IF NOT EXISTS idx_archived_reason ON archived_articles(archive_reason);
CREATE INDEX IF NOT EXISTS idx_archived_date ON archived_articles(archived_at);

-- ============================================================================
-- 4. CREATE FUNCTIONS FOR DEDUPLICATION
-- ============================================================================

-- Function to get duplicate statistics
CREATE OR REPLACE FUNCTION get_duplicate_statistics()
RETURNS TABLE(
    total_articles BIGINT,
    duplicate_articles BIGINT,
    duplicate_rate DECIMAL(5,2),
    total_groups BIGINT,
    avg_duplicates_per_group DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_articles,
        COUNT(CASE WHEN is_duplicate THEN 1 END)::BIGINT as duplicate_articles,
        ROUND(
            (COUNT(CASE WHEN is_duplicate THEN 1 END)::DECIMAL / COUNT(*)::DECIMAL) * 100, 2
        ) as duplicate_rate,
        COUNT(DISTINCT dg.group_id)::BIGINT as total_groups,
        ROUND(AVG(dg.duplicate_count), 2) as avg_duplicates_per_group
    FROM articles a
    LEFT JOIN duplicate_groups dg ON a.id = dg.original_article_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get articles by duplicate group
CREATE OR REPLACE FUNCTION get_articles_by_duplicate_group(group_id_param INTEGER)
RETURNS TABLE(
    article_id INTEGER,
    title TEXT,
    url VARCHAR(500),
    is_duplicate BOOLEAN,
    duplicate_of INTEGER,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.title,
        a.url,
        a.is_duplicate,
        a.duplicate_of,
        a.created_at
    FROM articles a
    WHERE a.id = (SELECT original_article_id FROM duplicate_groups WHERE group_id = group_id_param)
       OR a.duplicate_of = (SELECT original_article_id FROM duplicate_groups WHERE group_id = group_id_param)
    ORDER BY a.is_duplicate, a.created_at;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old duplicate groups
CREATE OR REPLACE FUNCTION cleanup_old_duplicate_groups(days_old INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM duplicate_groups 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_old
      AND duplicate_count = 0;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. CREATE TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Trigger for updating duplicate_groups updated_at
CREATE OR REPLACE FUNCTION update_duplicate_groups_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_duplicate_groups_updated_at
    BEFORE UPDATE ON duplicate_groups
    FOR EACH ROW
    EXECUTE FUNCTION update_duplicate_groups_updated_at();

-- Trigger for updating feed_health_metrics updated_at
CREATE OR REPLACE FUNCTION update_feed_health_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_feed_health_updated_at
    BEFORE UPDATE ON feed_health_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_feed_health_updated_at();

-- ============================================================================
-- 6. CREATE VIEWS FOR REPORTING
-- ============================================================================

-- View for duplicate analysis
CREATE OR REPLACE VIEW duplicate_analysis AS
SELECT 
    dg.group_id,
    dg.original_article_id,
    dg.duplicate_count,
    dg.similarity_type,
    dg.avg_confidence_score,
    dg.created_at,
    a.title as original_title,
    a.source as original_source,
    a.published_date as original_published_date
FROM duplicate_groups dg
JOIN articles a ON dg.original_article_id = a.id
ORDER BY dg.created_at DESC;

-- View for feed health summary
CREATE OR REPLACE VIEW feed_health_summary AS
SELECT 
    feed_name,
    feed_url,
    last_fetch_time,
    success_rate,
    avg_response_time_ms,
    error_count,
    is_active,
    CASE 
        WHEN last_fetch_time > NOW() - INTERVAL '1 hour' THEN 'healthy'
        WHEN last_fetch_time > NOW() - INTERVAL '24 hours' THEN 'warning'
        ELSE 'critical'
    END as health_status
FROM feed_health_metrics
ORDER BY health_status, last_fetch_time DESC;

-- View for content quality metrics
CREATE OR REPLACE VIEW content_quality_metrics AS
SELECT 
    source,
    COUNT(*) as total_articles,
    AVG(word_count) as avg_word_count,
    AVG(content_completeness_score) as avg_completeness,
    AVG(readability_score) as avg_readability,
    COUNT(CASE WHEN is_duplicate THEN 1 END) as duplicate_count,
    ROUND(
        (COUNT(CASE WHEN is_duplicate THEN 1 END)::DECIMAL / COUNT(*)::DECIMAL) * 100, 2
    ) as duplicate_rate
FROM articles
WHERE processing_status != 'raw'
GROUP BY source
ORDER BY total_articles DESC;

-- ============================================================================
-- 7. INSERT DEFAULT DATA
-- ============================================================================

-- Insert default feed health metrics for existing sources
INSERT INTO feed_health_metrics (feed_url, feed_name, is_active)
SELECT DISTINCT 
    'https://example.com/rss',  -- Placeholder URL
    source,
    TRUE
FROM articles 
WHERE source IS NOT NULL
  AND source != ''
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 8. GRANT PERMISSIONS
-- ============================================================================

-- Grant permissions to the database user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dockside_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dockside_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dockside_admin;

-- ============================================================================
-- 9. ADD COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE duplicate_groups IS 'Tracks groups of duplicate articles for analysis and management';
COMMENT ON TABLE feed_health_metrics IS 'Monitors RSS feed health and performance metrics';
COMMENT ON TABLE raw_articles_staging IS 'Staging area for raw articles before quality verification';
COMMENT ON TABLE archived_articles IS 'Long-term storage for archived articles';

COMMENT ON COLUMN articles.duplicate_of IS 'Reference to the original article if this is a duplicate';
COMMENT ON COLUMN articles.is_duplicate IS 'Flag indicating if this article is a duplicate';
COMMENT ON COLUMN articles.canonical_url IS 'Normalized URL without tracking parameters';
COMMENT ON COLUMN articles.url_hash IS 'Hash of the canonical URL for duplicate detection';
COMMENT ON COLUMN articles.detected_language IS 'Detected language of the article content';
COMMENT ON COLUMN articles.word_count IS 'Number of words in the article content';
COMMENT ON COLUMN articles.sentence_count IS 'Number of sentences in the article content';
COMMENT ON COLUMN articles.content_completeness_score IS 'Score indicating content completeness';
COMMENT ON COLUMN articles.readability_score IS 'Score indicating content readability';
COMMENT ON COLUMN articles.extracted_keywords IS 'Array of extracted keywords from content';
COMMENT ON COLUMN articles.keyword_scores IS 'JSONB object with keyword scores and metadata';

-- ============================================================================
-- 10. DISPLAY SCHEMA UPDATE SUMMARY
-- ============================================================================

-- Show all new columns added to articles table
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'articles' 
  AND column_name IN (
      'duplicate_of', 'is_duplicate', 'canonical_url', 'url_hash',
      'detected_language', 'language_confidence', 'word_count', 'sentence_count',
      'content_completeness_score', 'readability_score', 'extracted_keywords', 'keyword_scores'
  )
ORDER BY column_name;

-- Show all new tables created
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename IN (
    'duplicate_groups',
    'feed_health_metrics',
    'raw_articles_staging',
    'archived_articles'
)
ORDER BY tablename;

-- Show schema update completion
SELECT 'Deduplication system schema update completed successfully!' as status;
