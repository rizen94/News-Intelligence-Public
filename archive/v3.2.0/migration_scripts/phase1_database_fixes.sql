-- Migration Phase 1: Database Schema Fixes
-- Fixes all database inconsistencies and standardizes schema

-- =====================================================
-- 1. FIX COLUMN NAME INCONSISTENCIES
-- =====================================================

-- Fix articles table status column
ALTER TABLE articles RENAME COLUMN status TO processing_status;

-- Fix any other status columns that should be processing_status
DO $$
BEGIN
    -- Check if status column exists and rename it
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'articles' AND column_name = 'status') THEN
        ALTER TABLE articles RENAME COLUMN status TO processing_status;
    END IF;
END $$;

-- =====================================================
-- 2. FIX DATA TYPE INCONSISTENCIES
-- =====================================================

-- Ensure article IDs are integers
ALTER TABLE articles ALTER COLUMN id TYPE INTEGER;

-- Fix any string IDs that should be integers
UPDATE articles 
SET id = CAST(id AS INTEGER) 
WHERE id ~ '^[0-9]+$' AND id::TEXT != id::INTEGER::TEXT;

-- =====================================================
-- 3. ADD MISSING CONSTRAINTS
-- =====================================================

-- Add foreign key constraints
ALTER TABLE articles ADD CONSTRAINT articles_feed_id_fkey 
    FOREIGN KEY (feed_id) REFERENCES rss_feeds(id) ON DELETE SET NULL;

-- Add check constraints for processing_status
ALTER TABLE articles ADD CONSTRAINT articles_processing_status_check 
    CHECK (processing_status IN ('raw', 'processing', 'processed', 'error'));

-- Add check constraints for feed tier
ALTER TABLE rss_feeds ADD CONSTRAINT rss_feeds_tier_check 
    CHECK (tier IN (1, 2, 3));

-- Add check constraints for feed priority
ALTER TABLE rss_feeds ADD CONSTRAINT rss_feeds_priority_check 
    CHECK (priority BETWEEN 1 AND 10);

-- =====================================================
-- 4. STANDARDIZE TIMESTAMPS
-- =====================================================

-- Ensure all tables have created_at and updated_at
ALTER TABLE articles ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE articles ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE rss_feeds ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE rss_feeds ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;

-- Add updated_at trigger for articles
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS update_articles_updated_at ON articles;
CREATE TRIGGER update_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_rss_feeds_updated_at ON rss_feeds;
CREATE TRIGGER update_rss_feeds_updated_at
    BEFORE UPDATE ON rss_feeds
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 5. CREATE PERFORMANCE INDEXES
-- =====================================================

-- Articles table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_processing_status 
ON articles(processing_status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_created_at 
ON articles(created_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_source 
ON articles(source);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_feed_id 
ON articles(feed_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_published_at 
ON articles(published_at);

-- RSS feeds table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rss_feeds_is_active 
ON rss_feeds(is_active);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rss_feeds_tier 
ON rss_feeds(tier);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rss_feeds_category 
ON rss_feeds(category);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rss_feeds_status 
ON rss_feeds(status);

-- =====================================================
-- 6. CLEAN UP INCONSISTENT DATA
-- =====================================================

-- Fix any NULL processing_status values
UPDATE articles 
SET processing_status = 'raw' 
WHERE processing_status IS NULL;

-- Fix any invalid processing_status values
UPDATE articles 
SET processing_status = 'raw' 
WHERE processing_status NOT IN ('raw', 'processing', 'processed', 'error');

-- Fix any invalid tier values
UPDATE rss_feeds 
SET tier = 2 
WHERE tier NOT IN (1, 2, 3) OR tier IS NULL;

-- Fix any invalid priority values
UPDATE rss_feeds 
SET priority = 5 
WHERE priority < 1 OR priority > 10 OR priority IS NULL;

-- =====================================================
-- 7. ADD MISSING COLUMNS
-- =====================================================

-- Add missing columns to articles table if they don't exist
DO $$
BEGIN
    -- Add word_count column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'articles' AND column_name = 'word_count') THEN
        ALTER TABLE articles ADD COLUMN word_count INTEGER DEFAULT 0;
    END IF;
    
    -- Add reading_time column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'articles' AND column_name = 'reading_time') THEN
        ALTER TABLE articles ADD COLUMN reading_time INTEGER DEFAULT 0;
    END IF;
    
    -- Add feed_id column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'articles' AND column_name = 'feed_id') THEN
        ALTER TABLE articles ADD COLUMN feed_id INTEGER;
    END IF;
    
    -- Add tags column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'articles' AND column_name = 'tags') THEN
        ALTER TABLE articles ADD COLUMN tags JSONB DEFAULT '[]';
    END IF;
    
    -- Add sentiment_score column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'articles' AND column_name = 'sentiment_score') THEN
        ALTER TABLE articles ADD COLUMN sentiment_score NUMERIC(3,2);
    END IF;
    
    -- Add entities column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'articles' AND column_name = 'entities') THEN
        ALTER TABLE articles ADD COLUMN entities JSONB DEFAULT '{}';
    END IF;
    
    -- Add readability_score column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'articles' AND column_name = 'readability_score') THEN
        ALTER TABLE articles ADD COLUMN readability_score NUMERIC(3,2);
    END IF;
END $$;

-- =====================================================
-- 8. VALIDATE SCHEMA CHANGES
-- =====================================================

-- Verify all required columns exist
DO $$
DECLARE
    missing_columns TEXT[] := ARRAY[]::TEXT[];
    col TEXT;
    required_columns TEXT[] := ARRAY[
        'id', 'title', 'content', 'url', 'source', 'processing_status',
        'created_at', 'updated_at', 'word_count', 'reading_time', 
        'feed_id', 'tags', 'sentiment_score', 'entities', 'readability_score'
    ];
BEGIN
    FOREACH col IN ARRAY required_columns
    LOOP
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name = 'articles' AND column_name = col) THEN
            missing_columns := array_append(missing_columns, col);
        END IF;
    END LOOP;
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE EXCEPTION 'Missing required columns in articles table: %', array_to_string(missing_columns, ', ');
    END IF;
END $$;

-- Verify all required columns exist in rss_feeds
DO $$
DECLARE
    missing_columns TEXT[] := ARRAY[]::TEXT[];
    col TEXT;
    required_columns TEXT[] := ARRAY[
        'id', 'name', 'url', 'description', 'tier', 'priority',
        'language', 'country', 'category', 'subcategory', 'is_active',
        'status', 'update_frequency', 'max_articles_per_update',
        'success_rate', 'avg_response_time', 'reliability_score',
        'created_at', 'updated_at'
    ];
BEGIN
    FOREACH col IN ARRAY required_columns
    LOOP
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name = 'rss_feeds' AND column_name = col) THEN
            missing_columns := array_append(missing_columns, col);
        END IF;
    END LOOP;
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE EXCEPTION 'Missing required columns in rss_feeds table: %', array_to_string(missing_columns, ', ');
    END IF;
END $$;

-- =====================================================
-- 9. CREATE SCHEMA VALIDATION FUNCTION
-- =====================================================

CREATE OR REPLACE FUNCTION validate_schema()
RETURNS TABLE(
    table_name TEXT,
    column_name TEXT,
    data_type TEXT,
    is_nullable TEXT,
    column_default TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.table_name::TEXT,
        c.column_name::TEXT,
        c.data_type::TEXT,
        c.is_nullable::TEXT,
        c.column_default::TEXT
    FROM information_schema.columns c
    WHERE c.table_name IN ('articles', 'rss_feeds')
    ORDER BY c.table_name, c.ordinal_position;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 10. FINAL VALIDATION
-- =====================================================

-- Run schema validation
SELECT * FROM validate_schema();

-- Check for any remaining inconsistencies
SELECT 
    'articles' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN processing_status IS NULL THEN 1 END) as null_processing_status,
    COUNT(CASE WHEN created_at IS NULL THEN 1 END) as null_created_at,
    COUNT(CASE WHEN updated_at IS NULL THEN 1 END) as null_updated_at
FROM articles
UNION ALL
SELECT 
    'rss_feeds' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN tier IS NULL THEN 1 END) as null_tier,
    COUNT(CASE WHEN created_at IS NULL THEN 1 END) as null_created_at,
    COUNT(CASE WHEN updated_at IS NULL THEN 1 END) as null_updated_at
FROM rss_feeds;

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================

COMMENT ON TABLE articles IS 'Articles table - standardized schema with processing_status column';
COMMENT ON TABLE rss_feeds IS 'RSS feeds table - standardized schema with tier and priority columns';

-- Log migration completion
INSERT INTO system_logs (message, level, created_at) 
VALUES ('Phase 1 database migration completed successfully', 'INFO', CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;
