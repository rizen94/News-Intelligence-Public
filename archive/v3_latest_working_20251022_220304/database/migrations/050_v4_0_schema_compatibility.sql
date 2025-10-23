-- News Intelligence System v4.0 - Database Migration
-- Adds missing tables and columns for v4.0 domain architecture
-- Compatible with existing v3.0 schema

-- Migration: v4_0_schema_compatibility
-- Generated: 2025-10-22T18:00:00
-- Version: 4.0.0

BEGIN;

-- ============================================================================
-- ADD MISSING COLUMNS TO EXISTING TABLES
-- ============================================================================

-- Add missing columns to articles table
ALTER TABLE articles 
ADD COLUMN IF NOT EXISTS analysis_updated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS sentiment_label VARCHAR(50),
ADD COLUMN IF NOT EXISTS bias_score DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS bias_indicators JSONB;

-- Add missing columns to storylines table
ALTER TABLE storylines 
ADD COLUMN IF NOT EXISTS article_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS quality_score DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS analysis_summary TEXT;

-- ============================================================================
-- CREATE MISSING TABLES FOR v4.0 FUNCTIONALITY
-- ============================================================================

-- Create storyline_articles junction table
CREATE TABLE IF NOT EXISTS storyline_articles (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    added_by VARCHAR(100) DEFAULT 'system',
    relevance_score DECIMAL(3,2) DEFAULT 0.0,
    UNIQUE(storyline_id, article_id)
);

-- Create timeline_events table for storyline timeline generation
CREATE TABLE IF NOT EXISTS timeline_events (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_description TEXT NOT NULL,
    event_date TIMESTAMP NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Create user_profiles table for user management domain
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(200),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create user_preferences table for personalized experiences
CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    preference_type VARCHAR(50) NOT NULL,
    preference_value JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, preference_type)
);

-- Create system_metrics table for system monitoring domain
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,4) NOT NULL,
    metric_unit VARCHAR(20),
    metric_type VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Create system_alerts table for alerting
CREATE TABLE IF NOT EXISTS system_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    alert_level VARCHAR(20) NOT NULL,
    alert_message TEXT NOT NULL,
    alert_data JSONB DEFAULT '{}',
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100)
);

-- Create intelligence_insights table for intelligence hub domain
CREATE TABLE IF NOT EXISTS intelligence_insights (
    id SERIAL PRIMARY KEY,
    insight_type VARCHAR(50) NOT NULL,
    insight_title VARCHAR(300) NOT NULL,
    insight_description TEXT NOT NULL,
    insight_data JSONB NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.0,
    relevance_score DECIMAL(3,2) DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create trend_predictions table for predictive analytics
CREATE TABLE IF NOT EXISTS trend_predictions (
    id SERIAL PRIMARY KEY,
    prediction_type VARCHAR(50) NOT NULL,
    prediction_title VARCHAR(300) NOT NULL,
    prediction_description TEXT NOT NULL,
    prediction_data JSONB NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.0,
    predicted_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- ============================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Indexes for storyline_articles
CREATE INDEX IF NOT EXISTS idx_storyline_articles_storyline_id ON storyline_articles(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_article_id ON storyline_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_added_at ON storyline_articles(added_at);

-- Indexes for timeline_events
CREATE INDEX IF NOT EXISTS idx_timeline_events_storyline_id ON timeline_events(storyline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_article_id ON timeline_events(article_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_date ON timeline_events(event_date);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_type ON timeline_events(event_type);

-- Indexes for user_profiles
CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles(username);
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_is_active ON user_profiles(is_active);

-- Indexes for user_preferences
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_type ON user_preferences(preference_type);

-- Indexes for system_metrics
CREATE INDEX IF NOT EXISTS idx_system_metrics_name ON system_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_system_metrics_type ON system_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_system_metrics_recorded_at ON system_metrics(recorded_at);

-- Indexes for system_alerts
CREATE INDEX IF NOT EXISTS idx_system_alerts_type ON system_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_system_alerts_level ON system_alerts(alert_level);
CREATE INDEX IF NOT EXISTS idx_system_alerts_resolved ON system_alerts(is_resolved);
CREATE INDEX IF NOT EXISTS idx_system_alerts_created_at ON system_alerts(created_at);

-- Indexes for intelligence_insights
CREATE INDEX IF NOT EXISTS idx_intelligence_insights_type ON intelligence_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_intelligence_insights_active ON intelligence_insights(is_active);
CREATE INDEX IF NOT EXISTS idx_intelligence_insights_created_at ON intelligence_insights(created_at);

-- Indexes for trend_predictions
CREATE INDEX IF NOT EXISTS idx_trend_predictions_type ON trend_predictions(prediction_type);
CREATE INDEX IF NOT EXISTS idx_trend_predictions_active ON trend_predictions(is_active);
CREATE INDEX IF NOT EXISTS idx_trend_predictions_date ON trend_predictions(predicted_date);

-- ============================================================================
-- UPDATE EXISTING INDEXES FOR NEW COLUMNS
-- ============================================================================

-- Add index for new analysis_updated_at column
CREATE INDEX IF NOT EXISTS idx_articles_analysis_updated_at ON articles(analysis_updated_at);

-- Add index for new sentiment_label column
CREATE INDEX IF NOT EXISTS idx_articles_sentiment_label ON articles(sentiment_label);

-- Add index for new quality_score column in storylines
CREATE INDEX IF NOT EXISTS idx_storylines_quality_score ON storylines(quality_score);

-- ============================================================================
-- CREATE VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View for storyline summary with article counts
CREATE OR REPLACE VIEW storyline_summary AS
SELECT 
    s.id,
    s.title,
    s.description,
    s.status,
    s.created_at,
    s.updated_at,
    s.article_count,
    s.quality_score,
    COALESCE(COUNT(sa.article_id), 0) as actual_article_count,
    COALESCE(AVG(a.quality_score), 0) as avg_article_quality
FROM storylines s
LEFT JOIN storyline_articles sa ON s.id = sa.storyline_id
LEFT JOIN articles a ON sa.article_id = a.id
GROUP BY s.id, s.title, s.description, s.status, s.created_at, s.updated_at, s.article_count, s.quality_score;

-- View for article analysis status
CREATE OR REPLACE VIEW article_analysis_status AS
SELECT 
    a.id,
    a.title,
    a.source,
    a.created_at,
    a.analysis_updated_at,
    CASE 
        WHEN a.analysis_updated_at IS NULL THEN 'pending'
        WHEN a.analysis_updated_at < a.created_at THEN 'outdated'
        ELSE 'analyzed'
    END as analysis_status,
    a.sentiment_score,
    a.sentiment_label,
    a.quality_score
FROM articles a;

-- ============================================================================
-- INSERT DEFAULT DATA
-- ============================================================================

-- Insert default system user
INSERT INTO user_profiles (username, email, full_name, preferences) 
VALUES ('system', 'system@news-intelligence.local', 'System User', '{"role": "system", "permissions": ["admin"]}')
ON CONFLICT (username) DO NOTHING;

-- Insert default system metrics
INSERT INTO system_metrics (metric_name, metric_value, metric_unit, metric_type) VALUES
('system_startup', 1, 'count', 'system'),
('database_connected', 1, 'boolean', 'database'),
('llm_service_available', 1, 'boolean', 'llm')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- COMMIT TRANSACTION
-- ============================================================================

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify all tables exist
SELECT 
    table_name,
    CASE 
        WHEN table_name IN ('articles', 'storylines', 'rss_feeds', 'storyline_articles', 'timeline_events', 'user_profiles', 'user_preferences', 'system_metrics', 'system_alerts', 'intelligence_insights', 'trend_predictions') 
        THEN 'EXISTS' 
        ELSE 'MISSING' 
    END as status
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('articles', 'storylines', 'rss_feeds', 'storyline_articles', 'timeline_events', 'user_profiles', 'user_preferences', 'system_metrics', 'system_alerts', 'intelligence_insights', 'trend_predictions')
ORDER BY table_name;

-- Verify all columns exist in articles table
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'articles' 
AND column_name IN ('analysis_updated_at', 'sentiment_label', 'bias_score', 'bias_indicators')
ORDER BY column_name;

-- Verify all columns exist in storylines table
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'storylines' 
AND column_name IN ('article_count', 'quality_score', 'analysis_summary')
ORDER BY column_name;

-- Verify indexes exist
SELECT indexname, tablename 
FROM pg_indexes 
WHERE indexname LIKE 'idx_%' 
AND tablename IN ('storyline_articles', 'timeline_events', 'user_profiles', 'system_metrics', 'system_alerts', 'intelligence_insights', 'trend_predictions')
ORDER BY tablename, indexname;
