-- Migration 103: Complete Naming Consistency Fix
-- Aligns API endpoints, database columns, and frontend code with consistent snake_case naming
-- Created: October 22, 2025
-- Version: 4.0.3

-- ============================================================================
-- NAMING CONSISTENCY: Align API, Database, and Frontend
-- ============================================================================

-- Fix RSS Feeds table naming inconsistencies
DO $$
BEGIN
    -- Rename columns to match API and frontend expectations
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'rss_feeds' AND column_name = 'name') THEN
        ALTER TABLE rss_feeds RENAME COLUMN name TO feed_name;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'rss_feeds' AND column_name = 'url') THEN
        ALTER TABLE rss_feeds RENAME COLUMN url TO feed_url;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'rss_feeds' AND column_name = 'last_fetched') THEN
        ALTER TABLE rss_feeds RENAME COLUMN last_fetched TO last_fetched_at;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'rss_feeds' AND column_name = 'fetch_interval') THEN
        ALTER TABLE rss_feeds RENAME COLUMN fetch_interval TO fetch_interval_seconds;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'rss_feeds' AND column_name = 'last_error') THEN
        ALTER TABLE rss_feeds RENAME COLUMN last_error TO last_error_message;
    END IF;
    
    RAISE NOTICE 'RSS Feeds table naming consistency applied';
END $$;

-- Fix Articles table naming inconsistencies
DO $$
BEGIN
    -- Rename columns to match API and frontend expectations
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'language') THEN
        ALTER TABLE articles RENAME COLUMN language TO language_code;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'reading_time') THEN
        ALTER TABLE articles RENAME COLUMN reading_time TO reading_time_minutes;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'source') THEN
        ALTER TABLE articles RENAME COLUMN source TO source_domain;
    END IF;
    
    -- Add missing columns that API expects
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'excerpt') THEN
        ALTER TABLE articles ADD COLUMN excerpt TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'canonical_url') THEN
        ALTER TABLE articles ADD COLUMN canonical_url VARCHAR(1000);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'publisher') THEN
        ALTER TABLE articles ADD COLUMN publisher VARCHAR(255);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'discovered_at') THEN
        ALTER TABLE articles ADD COLUMN discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'sentiment_confidence') THEN
        ALTER TABLE articles ADD COLUMN sentiment_confidence DECIMAL(3,2) DEFAULT 0.0;
    END IF;
    
    RAISE NOTICE 'Articles table naming consistency applied';
END $$;

-- Fix Storylines table naming inconsistencies
DO $$
BEGIN
    -- Rename columns to match API and frontend expectations
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'created_by') THEN
        ALTER TABLE storylines RENAME COLUMN created_by TO created_by_user;
    END IF;
    
    -- Add missing columns that API expects
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'storyline_uuid') THEN
        ALTER TABLE storylines ADD COLUMN storyline_uuid VARCHAR(36);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'processing_status') THEN
        ALTER TABLE storylines ADD COLUMN processing_status VARCHAR(50) DEFAULT 'pending';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'completeness_score') THEN
        ALTER TABLE storylines ADD COLUMN completeness_score DECIMAL(3,2) DEFAULT 0.0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'coherence_score') THEN
        ALTER TABLE storylines ADD COLUMN coherence_score DECIMAL(3,2) DEFAULT 0.0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'total_entities') THEN
        ALTER TABLE storylines ADD COLUMN total_entities INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'total_events') THEN
        ALTER TABLE storylines ADD COLUMN total_events INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'time_span_days') THEN
        ALTER TABLE storylines ADD COLUMN time_span_days INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'timeline_events') THEN
        ALTER TABLE storylines ADD COLUMN timeline_events JSONB DEFAULT '[]';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'topic_clusters') THEN
        ALTER TABLE storylines ADD COLUMN topic_clusters JSONB DEFAULT '[]';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'sentiment_trends') THEN
        ALTER TABLE storylines ADD COLUMN sentiment_trends JSONB DEFAULT '{}';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'analysis_results') THEN
        ALTER TABLE storylines ADD COLUMN analysis_results JSONB DEFAULT '{}';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'last_analysis_at') THEN
        ALTER TABLE storylines ADD COLUMN last_analysis_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'analysis_version') THEN
        ALTER TABLE storylines ADD COLUMN analysis_version INTEGER DEFAULT 1;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'processing_errors') THEN
        ALTER TABLE storylines ADD COLUMN processing_errors JSONB DEFAULT '[]';
    END IF;
    
    RAISE NOTICE 'Storylines table naming consistency applied';
END $$;

-- ============================================================================
-- CREATE CONSISTENT API RESPONSE VIEWS
-- ============================================================================

-- Articles API Response View
CREATE OR REPLACE VIEW articles_api_response AS
SELECT 
    a.id,
    a.title,
    a.content,
    a.excerpt,
    a.url,
    a.canonical_url,
    a.published_at,
    a.discovered_at,
    a.author,
    a.publisher,
    a.source_domain,
    a.language_code,
    a.word_count,
    a.reading_time_minutes,
    a.content_hash,
    a.processing_status,
    a.processing_stage,
    a.processing_started_at,
    a.processing_completed_at,
    a.processing_error_message,
    a.quality_score,
    a.readability_score,
    a.bias_score,
    a.credibility_score,
    a.summary,
    a.sentiment_label,
    a.sentiment_score,
    a.sentiment_confidence,
    a.entities,
    a.topics,
    a.keywords,
    a.categories,
    a.tags,
    a.ml_data as metadata,
    a.analysis_results,
    a.created_at,
    a.updated_at,
    a.feed_id,
    rss.feed_name,
    rss.feed_url as rss_feed_url,
    COUNT(sa.storyline_id) as storyline_count,
    COUNT(atc.topic_cluster_id) as topic_cluster_count
FROM articles a
LEFT JOIN rss_feeds rss ON a.feed_id = rss.id
LEFT JOIN storyline_articles sa ON a.id = sa.article_id
LEFT JOIN article_topic_clusters atc ON a.id = atc.article_id
GROUP BY a.id, rss.feed_name, rss.feed_url;

-- RSS Feeds API Response View
CREATE OR REPLACE VIEW rss_feeds_api_response AS
SELECT 
    r.id,
    r.feed_name,
    r.feed_url,
    r.description,
    r.is_active,
    r.fetch_interval_seconds,
    r.last_fetched_at,
    r.error_count,
    r.last_error_message,
    r.success_rate,
    r.avg_response_time,
    r.tags,
    r.quality_score,
    r.created_at,
    r.updated_at,
    COUNT(a.id) as article_count,
    COUNT(CASE WHEN a.created_at >= CURRENT_DATE THEN a.id END) as articles_today
FROM rss_feeds r
LEFT JOIN articles a ON r.id = a.feed_id
GROUP BY r.id;

-- Storylines API Response View
CREATE OR REPLACE VIEW storylines_api_response AS
SELECT 
    s.id,
    s.storyline_uuid,
    s.title,
    s.description,
    s.status,
    s.processing_status,
    s.quality_score,
    s.completeness_score,
    s.coherence_score,
    s.article_count as total_articles,
    s.total_entities,
    s.total_events,
    s.time_span_days,
    s.key_entities,
    s.timeline_events,
    s.topic_clusters,
    s.sentiment_trends,
    s.analysis_results,
    s.last_analysis_at,
    s.analysis_version,
    s.processing_errors,
    s.created_at,
    s.updated_at,
    s.created_by_user,
    COUNT(sa.article_id) as article_count,
    MIN(a.published_at) as earliest_event_date,
    MAX(a.published_at) as latest_event_date
FROM storylines s
LEFT JOIN storyline_articles sa ON s.id = sa.storyline_id
LEFT JOIN articles a ON sa.article_id = a.id
GROUP BY s.id;

-- ============================================================================
-- UPDATE INDEXES FOR CONSISTENT NAMING
-- ============================================================================

-- Drop old indexes with inconsistent names
DROP INDEX IF EXISTS idx_articles_source;
DROP INDEX IF EXISTS idx_articles_language;
DROP INDEX IF EXISTS idx_articles_reading_time;

-- Create new indexes with consistent names
CREATE INDEX IF NOT EXISTS idx_articles_source_domain ON articles(source_domain);
CREATE INDEX IF NOT EXISTS idx_articles_language_code ON articles(language_code);
CREATE INDEX IF NOT EXISTS idx_articles_reading_time_minutes ON articles(reading_time_minutes);
CREATE INDEX IF NOT EXISTS idx_articles_discovered_at ON articles(discovered_at);
CREATE INDEX IF NOT EXISTS idx_articles_publisher ON articles(publisher);

-- RSS Feeds indexes
CREATE INDEX IF NOT EXISTS idx_rss_feeds_feed_name ON rss_feeds(feed_name);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_feed_url ON rss_feeds(feed_url);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_last_fetched_at ON rss_feeds(last_fetched_at);

-- Storylines indexes
CREATE INDEX IF NOT EXISTS idx_storylines_storyline_uuid ON storylines(storyline_uuid);
CREATE INDEX IF NOT EXISTS idx_storylines_processing_status ON storylines(processing_status);
CREATE INDEX IF NOT EXISTS idx_storylines_last_analysis_at ON storylines(last_analysis_at);

-- ============================================================================
-- CREATE API COMPATIBILITY FUNCTIONS
-- ============================================================================

-- Function to get articles with consistent API response format
CREATE OR REPLACE FUNCTION get_articles_api_response(
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0,
    p_status VARCHAR DEFAULT NULL,
    p_source VARCHAR DEFAULT NULL,
    p_category VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    success BOOLEAN,
    data JSONB,
    message TEXT,
    response_timestamp TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    articles_data JSONB;
    total_count INTEGER;
BEGIN
    -- Get total count
    SELECT COUNT(*) INTO total_count
    FROM articles_api_response
    WHERE (p_status IS NULL OR processing_status = p_status)
    AND (p_source IS NULL OR source_domain = p_source)
    AND (p_category IS NULL OR categories::text LIKE '%' || p_category || '%');
    
    -- Get articles data
    SELECT jsonb_agg(
        jsonb_build_object(
            'id', id,
            'title', title,
            'content', content,
            'excerpt', excerpt,
            'url', url,
            'canonical_url', canonical_url,
            'published_at', published_at,
            'discovered_at', discovered_at,
            'author', author,
            'publisher', publisher,
            'source_domain', source_domain,
            'language_code', language_code,
            'word_count', word_count,
            'reading_time_minutes', reading_time_minutes,
            'processing_status', processing_status,
            'processing_stage', processing_stage,
            'quality_score', quality_score,
            'readability_score', readability_score,
            'bias_score', bias_score,
            'credibility_score', credibility_score,
            'summary', summary,
            'sentiment_label', sentiment_label,
            'sentiment_score', sentiment_score,
            'sentiment_confidence', sentiment_confidence,
            'entities', entities,
            'topics', topics,
            'keywords', keywords,
            'categories', categories,
            'tags', tags,
            'metadata', ml_data,
            'analysis_results', analysis_results,
            'created_at', created_at,
            'updated_at', updated_at,
            'feed_name', feed_name,
            'storyline_count', storyline_count,
            'topic_cluster_count', topic_cluster_count
        )
    ) INTO articles_data
    FROM articles_api_response
    WHERE (p_status IS NULL OR processing_status = p_status)
    AND (p_source IS NULL OR source_domain = p_source)
    AND (p_category IS NULL OR categories::text LIKE '%' || p_category || '%')
    ORDER BY created_at DESC
    LIMIT p_limit OFFSET p_offset;
    
    RETURN QUERY SELECT 
        TRUE as success,
        jsonb_build_object(
            'articles', COALESCE(articles_data, '[]'::jsonb),
            'total', total_count,
            'page', (p_offset / p_limit) + 1,
            'limit', p_limit
        ) as data,
        'Articles retrieved successfully' as message,
        CURRENT_TIMESTAMP as response_timestamp;
END;
$$ LANGUAGE plpgsql;

-- Function to get RSS feeds with consistent API response format
CREATE OR REPLACE FUNCTION get_rss_feeds_api_response()
RETURNS TABLE (
    success BOOLEAN,
    data JSONB,
    message TEXT,
    response_timestamp TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    feeds_data JSONB;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'id', id,
            'feed_name', feed_name,
            'feed_url', feed_url,
            'description', description,
            'is_active', is_active,
            'fetch_interval_seconds', fetch_interval_seconds,
            'last_fetched_at', last_fetched_at,
            'error_count', error_count,
            'last_error_message', last_error_message,
            'success_rate', success_rate,
            'avg_response_time', avg_response_time,
            'tags', tags,
            'quality_score', quality_score,
            'created_at', created_at,
            'updated_at', updated_at,
            'article_count', article_count,
            'articles_today', articles_today
        )
    ) INTO feeds_data
    FROM rss_feeds_api_response
    ORDER BY feed_name;
    
    RETURN QUERY SELECT 
        TRUE as success,
        COALESCE(feeds_data, '[]'::jsonb) as data,
        'RSS feeds retrieved successfully' as message,
        CURRENT_TIMESTAMP as response_timestamp;
END;
$$ LANGUAGE plpgsql;

-- Function to get storylines with consistent API response format
CREATE OR REPLACE FUNCTION get_storylines_api_response()
RETURNS TABLE (
    success BOOLEAN,
    data JSONB,
    message TEXT,
    response_timestamp TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    storylines_data JSONB;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'id', id,
            'storyline_uuid', storyline_uuid,
            'title', title,
            'description', description,
            'status', status,
            'processing_status', processing_status,
            'quality_score', quality_score,
            'completeness_score', completeness_score,
            'coherence_score', coherence_score,
            'total_articles', article_count,
            'total_entities', total_entities,
            'total_events', total_events,
            'time_span_days', time_span_days,
            'key_entities', key_entities,
            'timeline_events', timeline_events,
            'topic_clusters', topic_clusters,
            'sentiment_trends', sentiment_trends,
            'analysis_results', analysis_results,
            'last_analysis_at', last_analysis_at,
            'analysis_version', analysis_version,
            'processing_errors', processing_errors,
            'created_at', created_at,
            'updated_at', updated_at,
            'created_by_user', created_by_user,
            'article_count', article_count,
            'earliest_event_date', earliest_event_date,
            'latest_event_date', latest_event_date
        )
    ) INTO storylines_data
    FROM storylines_api_response
    ORDER BY updated_at DESC;
    
    RETURN QUERY SELECT 
        TRUE as success,
        COALESCE(storylines_data, '[]'::jsonb) as data,
        'Storylines retrieved successfully' as message,
        CURRENT_TIMESTAMP as response_timestamp;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'v4.0 Naming Consistency Migration Completed Successfully';
    RAISE NOTICE 'Applied consistent snake_case naming across all components';
    RAISE NOTICE 'Created API response views for consistent data formatting';
    RAISE NOTICE 'Created API compatibility functions for consistent responses';
    RAISE NOTICE 'Updated indexes with consistent naming conventions';
    RAISE NOTICE 'API endpoints, database columns, and frontend code now aligned';
END $$;
