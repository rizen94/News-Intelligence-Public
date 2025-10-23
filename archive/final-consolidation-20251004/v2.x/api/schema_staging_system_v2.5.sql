-- News Intelligence System v2.5 - Staging System Database Schema
-- This script creates the staging system tables for quality-controlled article processing
-- Includes article staging, quality validation, and workflow management

-- ============================================================================
-- 1. CREATE ARTICLE STAGING TABLE
-- ============================================================================

-- Create the main staging table
CREATE TABLE IF NOT EXISTS article_staging (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url VARCHAR(500) UNIQUE NOT NULL,
    source VARCHAR(100) NOT NULL,
    published_date TIMESTAMP,
    collected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash VARCHAR(64) NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    stage VARCHAR(20) DEFAULT 'raw',
    stage_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_attempts INTEGER DEFAULT 0,
    last_error TEXT,
    metadata JSONB DEFAULT '{}',
    quality_score DECIMAL(5,3),
    language_detected VARCHAR(10),
    validation_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_staging_stage ON article_staging(stage);
CREATE INDEX IF NOT EXISTS idx_staging_content_hash ON article_staging(content_hash);
CREATE INDEX IF NOT EXISTS idx_staging_url_hash ON article_staging(url_hash);
CREATE INDEX IF NOT EXISTS idx_staging_collected_date ON article_staging(collected_date);
CREATE INDEX IF NOT EXISTS idx_staging_quality_score ON article_staging(quality_score);
CREATE INDEX IF NOT EXISTS idx_staging_language ON article_staging(language_detected);
CREATE INDEX IF NOT EXISTS idx_staging_validation_status ON article_staging(validation_status);

-- ============================================================================
-- 2. CREATE STAGING WORKFLOW LOG TABLE
-- ============================================================================

-- Track workflow progression and decisions
CREATE TABLE IF NOT EXISTS staging_workflow_log (
    id SERIAL PRIMARY KEY,
    staged_article_id INTEGER REFERENCES article_staging(id) ON DELETE CASCADE,
    from_stage VARCHAR(20) NOT NULL,
    to_stage VARCHAR(20) NOT NULL,
    decision_reason TEXT,
    quality_metrics JSONB,
    language_detection JSONB,
    validation_results JSONB,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for workflow tracking
CREATE INDEX IF NOT EXISTS idx_workflow_staged_article_id ON staging_workflow_log(staged_article_id);
CREATE INDEX IF NOT EXISTS idx_workflow_stage_transition ON staging_workflow_log(from_stage, to_stage);
CREATE INDEX IF NOT EXISTS idx_workflow_created_at ON staging_workflow_log(created_at);

-- ============================================================================
-- 3. CREATE QUALITY VALIDATION RESULTS TABLE
-- ============================================================================

-- Store detailed quality validation results
CREATE TABLE IF NOT EXISTS quality_validation_results (
    id SERIAL PRIMARY KEY,
    staged_article_id INTEGER REFERENCES article_staging(id) ON DELETE CASCADE,
    validation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_length INTEGER,
    word_count INTEGER,
    sentence_count INTEGER,
    paragraph_count INTEGER,
    average_sentence_length DECIMAL(5,2),
    average_word_length DECIMAL(5,2),
    unique_words INTEGER,
    vocabulary_diversity DECIMAL(5,3),
    readability_score DECIMAL(5,2),
    content_completeness DECIMAL(5,3),
    overall_quality_score DECIMAL(5,3),
    validation_status VARCHAR(20),
    issues JSONB,
    recommendations JSONB,
    processing_recommendation VARCHAR(20)
);

-- Create indexes for quality validation
CREATE INDEX IF NOT EXISTS idx_quality_staged_article_id ON quality_validation_results(staged_article_id);
CREATE INDEX IF NOT EXISTS idx_quality_validation_status ON quality_validation_results(validation_status);
CREATE INDEX IF NOT EXISTS idx_quality_score ON quality_validation_results(overall_quality_score);

-- ============================================================================
-- 4. CREATE LANGUAGE DETECTION RESULTS TABLE
-- ============================================================================

-- Store language detection results and confidence scores
CREATE TABLE IF NOT EXISTS language_detection_results (
    id SERIAL PRIMARY KEY,
    staged_article_id INTEGER REFERENCES article_staging(id) ON DELETE CASCADE,
    detection_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_language VARCHAR(10),
    confidence_score DECIMAL(5,3),
    alternative_languages JSONB,
    is_english BOOLEAN,
    is_reliable BOOLEAN,
    detection_method VARCHAR(50),
    processing_recommendation VARCHAR(20),
    text_sample TEXT
);

-- Create indexes for language detection
CREATE INDEX IF NOT EXISTS idx_language_staged_article_id ON language_detection_results(staged_article_id);
CREATE INDEX IF NOT EXISTS idx_language_detected ON language_detection_results(detected_language);
CREATE INDEX IF NOT EXISTS idx_language_confidence ON language_detection_results(confidence_score);
CREATE INDEX IF NOT EXISTS idx_language_is_english ON language_detection_results(is_english);

-- ============================================================================
-- 5. CREATE CONTENT CLEANING RESULTS TABLE
-- ============================================================================

-- Store content cleaning results and metadata
CREATE TABLE IF NOT EXISTS content_cleaning_results (
    id SERIAL PRIMARY KEY,
    staged_article_id INTEGER REFERENCES article_staging(id) ON DELETE CASCADE,
    cleaning_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    original_length INTEGER,
    cleaned_length INTEGER,
    cleaning_actions JSONB,
    quality_score DECIMAL(5,3),
    encoding_fixed BOOLEAN,
    html_removed BOOLEAN,
    normalized BOOLEAN,
    cleaning_duration_ms INTEGER
);

-- Create indexes for content cleaning
CREATE INDEX IF NOT EXISTS idx_cleaning_staged_article_id ON content_cleaning_results(staged_article_id);
CREATE INDEX IF NOT EXISTS idx_cleaning_quality_score ON content_cleaning_results(quality_score);
CREATE INDEX IF NOT EXISTS idx_cleaning_timestamp ON content_cleaning_results(cleaning_timestamp);

-- ============================================================================
-- 6. CREATE STAGING STATISTICS VIEW
-- ============================================================================

-- Create a view for easy staging statistics
CREATE OR REPLACE VIEW staging_statistics AS
SELECT 
    stage,
    COUNT(*) as article_count,
    AVG(quality_score) as avg_quality_score,
    AVG(processing_attempts) as avg_processing_attempts,
    COUNT(CASE WHEN last_error IS NOT NULL THEN 1 END) as error_count,
    MIN(created_at) as oldest_article,
    MAX(created_at) as newest_article
FROM article_staging
GROUP BY stage;

-- ============================================================================
-- 7. CREATE STAGING HEALTH VIEW
-- ============================================================================

-- Create a view for staging system health monitoring
CREATE OR REPLACE VIEW staging_health AS
SELECT 
    'total_articles' as metric,
    COUNT(*) as value
FROM article_staging
UNION ALL
SELECT 
    'failed_articles',
    COUNT(*)
FROM article_staging
WHERE stage = 'failed'
UNION ALL
SELECT 
    'ready_articles',
    COUNT(*)
FROM article_staging
WHERE stage = 'ready'
UNION ALL
SELECT 
    'avg_processing_time_minutes',
    COALESCE(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/60), 0)
FROM article_staging
WHERE stage IN ('ready', 'failed')
UNION ALL
SELECT 
    'articles_last_24h',
    COUNT(*)
FROM article_staging
WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '24 hours';

-- ============================================================================
-- 8. CREATE STAGING CLEANUP FUNCTION
-- ============================================================================

-- Function to clean up old staged articles
CREATE OR REPLACE FUNCTION cleanup_old_staged_articles(days_old INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM article_staging 
    WHERE stage IN ('ready', 'failed') 
    AND updated_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * days_old;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. CREATE STAGING PROMOTION FUNCTION
-- ============================================================================

-- Function to promote ready articles to main articles table
CREATE OR REPLACE FUNCTION promote_staged_article(staged_article_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    article_data RECORD;
    new_article_id INTEGER;
BEGIN
    -- Get staged article data
    SELECT * INTO article_data 
    FROM article_staging 
    WHERE id = staged_article_id AND stage = 'ready';
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Insert into main articles table
    INSERT INTO articles (
        title, content, url, source, published_date, collected_date,
        content_hash, url_hash, detected_language, quality_score,
        validation_status, metadata, processing_status
    ) VALUES (
        article_data.title,
        article_data.content,
        article_data.url,
        article_data.source,
        article_data.published_date,
        article_data.collected_date,
        article_data.content_hash,
        article_data.url_hash,
        article_data.language_detected,
        article_data.quality_score,
        article_data.validation_status,
        article_data.metadata,
        'staged'
    ) RETURNING id INTO new_article_id;
    
    -- Remove from staging
    DELETE FROM article_staging WHERE id = staged_article_id;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. CREATE STAGING RETRY FUNCTION
-- ============================================================================

-- Function to retry failed articles
CREATE OR REPLACE FUNCTION retry_failed_staged_articles(max_attempts INTEGER DEFAULT 3)
RETURNS INTEGER AS $$
DECLARE
    retry_count INTEGER;
BEGIN
    UPDATE article_staging 
    SET stage = 'raw', 
        stage_timestamp = CURRENT_TIMESTAMP, 
        updated_at = CURRENT_TIMESTAMP
    WHERE stage = 'failed' 
    AND processing_attempts < max_attempts;
    
    GET DIAGNOSTICS retry_count = ROW_COUNT;
    
    RETURN retry_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 11. GRANT PERMISSIONS
-- ============================================================================

-- Grant permissions to the newsapp user
GRANT ALL PRIVILEGES ON TABLE article_staging TO newsapp;
GRANT ALL PRIVILEGES ON TABLE staging_workflow_log TO newsapp;
GRANT ALL PRIVILEGES ON TABLE quality_validation_results TO newsapp;
GRANT ALL PRIVILEGES ON TABLE language_detection_results TO newsapp;
GRANT ALL PRIVILEGES ON TABLE content_cleaning_results TO newsapp;
GRANT ALL PRIVILEGES ON TABLE staging_statistics TO newsapp;
GRANT ALL PRIVILEGES ON TABLE staging_health TO newsapp;

-- Grant execute permissions on functions
GRANT EXECUTE ON FUNCTION cleanup_old_staged_articles(INTEGER) TO newsapp;
GRANT EXECUTE ON FUNCTION promote_staged_article(INTEGER) TO newsapp;
GRANT EXECUTE ON FUNCTION retry_failed_staged_articles(INTEGER) TO newsapp;

-- ============================================================================
-- 12. INSERT INITIAL DATA
-- ============================================================================

-- Insert staging workflow configuration
INSERT INTO article_staging (title, content, url, source, stage, content_hash, url_hash)
VALUES (
    'STAGING_SYSTEM_CONFIG',
    'This is a system configuration record for the staging system',
    'https://system.config/staging',
    'system',
    'ready',
    'config_hash_placeholder',
    'config_url_hash_placeholder'
) ON CONFLICT (url) DO NOTHING;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Staging System Schema v2.5 created successfully!';
    RAISE NOTICE 'Tables created: article_staging, staging_workflow_log, quality_validation_results, language_detection_results, content_cleaning_results';
    RAISE NOTICE 'Views created: staging_statistics, staging_health';
    RAISE NOTICE 'Functions created: cleanup_old_staged_articles, promote_staged_article, retry_failed_staged_articles';
    RAISE NOTICE 'All permissions granted to newsapp user';
END $$;
