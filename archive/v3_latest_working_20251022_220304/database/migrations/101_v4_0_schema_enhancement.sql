-- Migration 101: v4.0 Schema Enhancement (Incremental)
-- Enhances existing schema with consistent naming, pipeline processing, and topic clustering
-- Works with existing tables and data
-- Created: October 22, 2025
-- Version: 4.0.1

-- ============================================================================
-- SCHEMA ENHANCEMENT: Add Missing Features to Existing Schema
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================================
-- ENHANCE EXISTING TABLES
-- ============================================================================

-- Add missing columns to articles table
DO $$ 
BEGIN
    -- Add UUID if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'article_uuid') THEN
        ALTER TABLE articles ADD COLUMN article_uuid UUID DEFAULT uuid_generate_v4();
    END IF;
    
    -- Add processing stage tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'processing_stage') THEN
        ALTER TABLE articles ADD COLUMN processing_stage VARCHAR(50) DEFAULT 'ingestion' CHECK (processing_stage IN (
            'ingestion', 'content_analysis', 'sentiment_analysis', 'entity_extraction',
            'summarization', 'topic_clustering', 'quality_assessment', 'completed'
        ));
    END IF;
    
    -- Add processing timestamps
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'processing_started_at') THEN
        ALTER TABLE articles ADD COLUMN processing_started_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'processing_completed_at') THEN
        ALTER TABLE articles ADD COLUMN processing_completed_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'processing_error_message') THEN
        ALTER TABLE articles ADD COLUMN processing_error_message TEXT;
    END IF;
    
    -- Add quality metrics
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'credibility_score') THEN
        ALTER TABLE articles ADD COLUMN credibility_score DECIMAL(3,2) DEFAULT 0.0 CHECK (credibility_score >= 0.0 AND credibility_score <= 1.0);
    END IF;
    
    -- Add content analysis fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'excerpt') THEN
        ALTER TABLE articles ADD COLUMN excerpt TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'canonical_url') THEN
        ALTER TABLE articles ADD COLUMN canonical_url VARCHAR(1000);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'publisher') THEN
        ALTER TABLE articles ADD COLUMN publisher VARCHAR(255);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'source_domain') THEN
        ALTER TABLE articles ADD COLUMN source_domain VARCHAR(255);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'discovered_at') THEN
        ALTER TABLE articles ADD COLUMN discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    END IF;
    
    -- Add sentiment confidence
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'sentiment_confidence') THEN
        ALTER TABLE articles ADD COLUMN sentiment_confidence DECIMAL(3,2) DEFAULT 0.0 CHECK (sentiment_confidence >= 0.0 AND sentiment_confidence <= 1.0);
    END IF;
    
    -- Add structured data fields (ensure JSONB)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'topics') THEN
        ALTER TABLE articles ADD COLUMN topics JSONB DEFAULT '[]';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'keywords') THEN
        ALTER TABLE articles ADD COLUMN keywords JSONB DEFAULT '[]';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'categories') THEN
        ALTER TABLE articles ADD COLUMN categories JSONB DEFAULT '[]';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'analysis_results') THEN
        ALTER TABLE articles ADD COLUMN analysis_results JSONB DEFAULT '{}';
    END IF;
    
    RAISE NOTICE 'Articles table enhanced successfully';
END $$;

-- Convert existing JSON columns to JSONB for consistency
DO $$
BEGIN
    -- Convert tags column to JSONB if it's JSON
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'tags' AND data_type = 'json') THEN
        ALTER TABLE articles ALTER COLUMN tags TYPE JSONB USING tags::JSONB;
        RAISE NOTICE 'Converted articles.tags from JSON to JSONB';
    END IF;
    
    -- Convert entities column to JSONB if it's JSON
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'entities' AND data_type = 'json') THEN
        ALTER TABLE articles ALTER COLUMN entities TYPE JSONB USING entities::JSONB;
        RAISE NOTICE 'Converted articles.entities from JSON to JSONB';
    END IF;
    
    -- Convert ml_data column to JSONB if it's JSON
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'ml_data' AND data_type = 'json') THEN
        ALTER TABLE articles ALTER COLUMN ml_data TYPE JSONB USING ml_data::JSONB;
        RAISE NOTICE 'Converted articles.ml_data from JSON to JSONB';
    END IF;
END $$;

-- Enhance storylines table
DO $$ 
BEGIN
    -- Add UUID if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'storyline_uuid') THEN
        ALTER TABLE storylines ADD COLUMN storyline_uuid UUID DEFAULT uuid_generate_v4();
    END IF;
    
    -- Add processing status tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'processing_status') THEN
        ALTER TABLE storylines ADD COLUMN processing_status VARCHAR(50) DEFAULT 'pending' CHECK (processing_status IN (
            'pending', 'analyzing', 'timeline_generation', 'rag_analysis', 'completed', 'failed'
        ));
    END IF;
    
    -- Add quality metrics
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'completeness_score') THEN
        ALTER TABLE storylines ADD COLUMN completeness_score DECIMAL(3,2) DEFAULT 0.0 CHECK (completeness_score >= 0.0 AND completeness_score <= 1.0);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'coherence_score') THEN
        ALTER TABLE storylines ADD COLUMN coherence_score DECIMAL(3,2) DEFAULT 0.0 CHECK (coherence_score >= 0.0 AND coherence_score <= 1.0);
    END IF;
    
    -- Add content analysis fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'total_entities') THEN
        ALTER TABLE storylines ADD COLUMN total_entities INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'total_events') THEN
        ALTER TABLE storylines ADD COLUMN total_events INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'time_span_days') THEN
        ALTER TABLE storylines ADD COLUMN time_span_days INTEGER DEFAULT 0;
    END IF;
    
    -- Add structured data fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'key_entities') THEN
        ALTER TABLE storylines ADD COLUMN key_entities JSONB DEFAULT '{}';
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
    
    -- Add processing metadata
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'last_analysis_at') THEN
        ALTER TABLE storylines ADD COLUMN last_analysis_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'analysis_version') THEN
        ALTER TABLE storylines ADD COLUMN analysis_version INTEGER DEFAULT 1;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storylines' AND column_name = 'processing_errors') THEN
        ALTER TABLE storylines ADD COLUMN processing_errors JSONB DEFAULT '[]';
    END IF;
    
    RAISE NOTICE 'Storylines table enhanced successfully';
END $$;

-- ============================================================================
-- CREATE NEW PIPELINE PROCESSING TABLES
-- ============================================================================

-- Processing Pipeline Stages
CREATE TABLE IF NOT EXISTS processing_stages (
    id SERIAL PRIMARY KEY,
    stage_name VARCHAR(50) UNIQUE NOT NULL,
    stage_description TEXT,
    stage_order INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Article Processing Pipeline Tracking
CREATE TABLE IF NOT EXISTS article_processing_log (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    processing_stage_id INTEGER NOT NULL REFERENCES processing_stages(id),
    stage_name VARCHAR(50) NOT NULL,
    
    -- Processing Details
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    processing_time_ms INTEGER,
    
    -- Results
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    result_data JSONB DEFAULT '{}',
    
    -- Metadata
    processor_version VARCHAR(50),
    resource_usage JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_processing_time CHECK (processing_time_ms >= 0)
);

-- Storyline Processing Pipeline Tracking
CREATE TABLE IF NOT EXISTS storyline_processing_log (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    processing_stage_id INTEGER NOT NULL REFERENCES processing_stages(id),
    stage_name VARCHAR(50) NOT NULL,
    
    -- Processing Details
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    processing_time_ms INTEGER,
    
    -- Results
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    result_data JSONB DEFAULT '{}',
    
    -- Metadata
    processor_version VARCHAR(50),
    resource_usage JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_storyline_processing_time CHECK (processing_time_ms >= 0)
);

-- ============================================================================
-- TOPIC CLUSTERING SYSTEM
-- ============================================================================

-- Topic Clusters (Word Cloud Foundation)
CREATE TABLE IF NOT EXISTS topic_clusters (
    id SERIAL PRIMARY KEY,
    cluster_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Cluster Information
    cluster_name VARCHAR(200) NOT NULL,
    cluster_description TEXT,
    cluster_keywords JSONB DEFAULT '[]',
    
    -- Clustering Metadata
    cluster_type VARCHAR(50) DEFAULT 'semantic' CHECK (cluster_type IN (
        'semantic', 'temporal', 'geographic', 'entity_based', 'sentiment_based'
    )),
    cluster_algorithm VARCHAR(100),
    cluster_version INTEGER DEFAULT 1,
    
    -- Quality Metrics
    coherence_score DECIMAL(3,2) DEFAULT 0.0,
    stability_score DECIMAL(3,2) DEFAULT 0.0,
    relevance_score DECIMAL(3,2) DEFAULT 0.0,
    
    -- Statistics
    article_count INTEGER DEFAULT 0,
    total_word_frequency INTEGER DEFAULT 0,
    average_sentiment DECIMAL(3,2) DEFAULT 0.0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_cluster_scores CHECK (
        coherence_score >= 0.0 AND coherence_score <= 1.0 AND
        stability_score >= 0.0 AND stability_score <= 1.0 AND
        relevance_score >= 0.0 AND relevance_score <= 1.0
    )
);

-- Article-Topic Cluster Relationships
CREATE TABLE IF NOT EXISTS article_topic_clusters (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    topic_cluster_id INTEGER NOT NULL REFERENCES topic_clusters(id) ON DELETE CASCADE,
    
    -- Relationship Strength
    relevance_score DECIMAL(3,2) NOT NULL,
    confidence_score DECIMAL(3,2) NOT NULL,
    
    -- Metadata
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    assignment_method VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_relevance_scores CHECK (
        relevance_score >= 0.0 AND relevance_score <= 1.0 AND
        confidence_score >= 0.0 AND confidence_score <= 1.0
    ),
    UNIQUE(article_id, topic_cluster_id)
);

-- Topic Keywords (Word Cloud Data)
CREATE TABLE IF NOT EXISTS topic_keywords (
    id SERIAL PRIMARY KEY,
    topic_cluster_id INTEGER NOT NULL REFERENCES topic_clusters(id) ON DELETE CASCADE,
    
    -- Keyword Information
    keyword VARCHAR(200) NOT NULL,
    keyword_type VARCHAR(50) DEFAULT 'general' CHECK (keyword_type IN (
        'general', 'entity', 'location', 'organization', 'person', 'concept'
    )),
    
    -- Frequency and Importance
    frequency_count INTEGER DEFAULT 1,
    importance_score DECIMAL(3,2) DEFAULT 0.0,
    tf_idf_score DECIMAL(6,4) DEFAULT 0.0,
    
    -- Metadata
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_keyword_scores CHECK (
        importance_score >= 0.0 AND importance_score <= 1.0 AND
        tf_idf_score >= 0.0
    ),
    UNIQUE(topic_cluster_id, keyword)
);

-- ============================================================================
-- ENHANCE EXISTING RELATIONSHIP TABLES
-- ============================================================================

-- Enhance storyline_articles table if it exists
DO $$
BEGIN
    -- Add relationship metadata if columns don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storyline_articles' AND column_name = 'relevance_score') THEN
        ALTER TABLE storyline_articles ADD COLUMN relevance_score DECIMAL(3,2) DEFAULT 0.0 CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storyline_articles' AND column_name = 'confidence_score') THEN
        ALTER TABLE storyline_articles ADD COLUMN confidence_score DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storyline_articles' AND column_name = 'relationship_type') THEN
        ALTER TABLE storyline_articles ADD COLUMN relationship_type VARCHAR(50) DEFAULT 'related' CHECK (relationship_type IN (
            'related', 'core', 'supporting', 'context', 'background'
        ));
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storyline_articles' AND column_name = 'event_date') THEN
        ALTER TABLE storyline_articles ADD COLUMN event_date DATE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storyline_articles' AND column_name = 'chronological_order') THEN
        ALTER TABLE storyline_articles ADD COLUMN chronological_order INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storyline_articles' AND column_name = 'added_by') THEN
        ALTER TABLE storyline_articles ADD COLUMN added_by VARCHAR(100);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'storyline_articles' AND column_name = 'metadata') THEN
        ALTER TABLE storyline_articles ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
    
    RAISE NOTICE 'Storyline articles table enhanced';
END $$;

-- ============================================================================
-- ENHANCE SYSTEM MONITORING TABLES
-- ============================================================================

-- Enhance system_metrics table if it exists
DO $$
BEGIN
    -- Add metric type if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_metrics' AND column_name = 'metric_type') THEN
        ALTER TABLE system_metrics ADD COLUMN metric_type VARCHAR(50) DEFAULT 'gauge' CHECK (metric_type IN (
            'gauge', 'counter', 'histogram', 'summary'
        ));
    END IF;
    
    -- Add labels if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_metrics' AND column_name = 'labels') THEN
        ALTER TABLE system_metrics ADD COLUMN labels JSONB DEFAULT '{}';
    END IF;
    
    RAISE NOTICE 'System metrics table enhanced';
END $$;

-- Enhance system_alerts table if it exists
DO $$
BEGIN
    -- Add UUID if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_alerts' AND column_name = 'alert_uuid') THEN
        ALTER TABLE system_alerts ADD COLUMN alert_uuid UUID DEFAULT uuid_generate_v4();
    END IF;
    
    -- Add alert data if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_alerts' AND column_name = 'alert_data') THEN
        ALTER TABLE system_alerts ADD COLUMN alert_data JSONB DEFAULT '{}';
    END IF;
    
    -- Add resolution data if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_alerts' AND column_name = 'resolution_data') THEN
        ALTER TABLE system_alerts ADD COLUMN resolution_data JSONB DEFAULT '{}';
    END IF;
    
    -- Add source component if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_alerts' AND column_name = 'source_component') THEN
        ALTER TABLE system_alerts ADD COLUMN source_component VARCHAR(100);
    END IF;
    
    RAISE NOTICE 'System alerts table enhanced';
END $$;

-- ============================================================================
-- ENHANCE USER MANAGEMENT TABLES
-- ============================================================================

-- Enhance user_profiles table if it exists
DO $$
BEGIN
    -- Add UUID if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'user_uuid') THEN
        ALTER TABLE user_profiles ADD COLUMN user_uuid UUID DEFAULT uuid_generate_v4();
    END IF;
    
    -- Add password hash if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'password_hash') THEN
        ALTER TABLE user_profiles ADD COLUMN password_hash VARCHAR(255);
    END IF;
    
    -- Add full name if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'full_name') THEN
        ALTER TABLE user_profiles ADD COLUMN full_name VARCHAR(255);
    END IF;
    
    -- Add status fields if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'is_active') THEN
        ALTER TABLE user_profiles ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'is_verified') THEN
        ALTER TABLE user_profiles ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'last_login_at') THEN
        ALTER TABLE user_profiles ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    -- Add preferences if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'preferences') THEN
        ALTER TABLE user_profiles ADD COLUMN preferences JSONB DEFAULT '{}';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'notification_settings') THEN
        ALTER TABLE user_profiles ADD COLUMN notification_settings JSONB DEFAULT '{}';
    END IF;
    
    -- Add roles if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_profiles' AND column_name = 'roles') THEN
        ALTER TABLE user_profiles ADD COLUMN roles JSONB DEFAULT '["user"]';
    END IF;
    
    RAISE NOTICE 'User profiles table enhanced';
END $$;

-- ============================================================================
-- CREATE INTELLIGENCE HUB TABLES
-- ============================================================================

-- Intelligence Reports
CREATE TABLE IF NOT EXISTS intelligence_reports (
    id SERIAL PRIMARY KEY,
    report_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Report Information
    report_id VARCHAR(16) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    content JSONB NOT NULL,
    
    -- Report Status
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'review', 'published', 'archived'
    )),
    
    -- Analysis Context
    analysis_type VARCHAR(100),
    analysis_method VARCHAR(100),
    confidence_score DECIMAL(3,2) DEFAULT 0.0,
    
    -- Relationships
    related_storylines JSONB DEFAULT '[]',
    source_articles JSONB DEFAULT '[]',
    
    -- Metadata
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    generated_by VARCHAR(100)
);

-- ============================================================================
-- CREATE PERFORMANCE INDEXES
-- ============================================================================

-- Articles indexes
CREATE INDEX IF NOT EXISTS idx_articles_processing_status ON articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_articles_processing_stage ON articles(processing_stage);
CREATE INDEX IF NOT EXISTS idx_articles_article_uuid ON articles(article_uuid);
CREATE INDEX IF NOT EXISTS idx_articles_source_domain ON articles(source_domain);
CREATE INDEX IF NOT EXISTS idx_articles_discovered_at ON articles(discovered_at);

-- GIN Indexes for JSONB columns
CREATE INDEX IF NOT EXISTS idx_articles_topics_gin ON articles USING GIN (topics);
CREATE INDEX IF NOT EXISTS idx_articles_keywords_gin ON articles USING GIN (keywords);
CREATE INDEX IF NOT EXISTS idx_articles_categories_gin ON articles USING GIN (categories);
CREATE INDEX IF NOT EXISTS idx_articles_analysis_results_gin ON articles USING GIN (analysis_results);

-- Storylines indexes
CREATE INDEX IF NOT EXISTS idx_storylines_processing_status ON storylines(processing_status);
CREATE INDEX IF NOT EXISTS idx_storylines_storyline_uuid ON storylines(storyline_uuid);
CREATE INDEX IF NOT EXISTS idx_storylines_last_analysis_at ON storylines(last_analysis_at);

-- GIN Indexes for Storylines JSONB
CREATE INDEX IF NOT EXISTS idx_storylines_key_entities_gin ON storylines USING GIN (key_entities);
CREATE INDEX IF NOT EXISTS idx_storylines_timeline_events_gin ON storylines USING GIN (timeline_events);
CREATE INDEX IF NOT EXISTS idx_storylines_topic_clusters_gin ON storylines USING GIN (topic_clusters);
CREATE INDEX IF NOT EXISTS idx_storylines_sentiment_trends_gin ON storylines USING GIN (sentiment_trends);
CREATE INDEX IF NOT EXISTS idx_storylines_analysis_results_gin ON storylines USING GIN (analysis_results);

-- Processing Pipeline Indexes
CREATE INDEX IF NOT EXISTS idx_article_processing_log_article_id ON article_processing_log(article_id);
CREATE INDEX IF NOT EXISTS idx_article_processing_log_stage ON article_processing_log(stage_name);
CREATE INDEX IF NOT EXISTS idx_article_processing_log_started_at ON article_processing_log(started_at);
CREATE INDEX IF NOT EXISTS idx_article_processing_log_success ON article_processing_log(success);

CREATE INDEX IF NOT EXISTS idx_storyline_processing_log_storyline_id ON storyline_processing_log(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_processing_log_stage ON storyline_processing_log(stage_name);
CREATE INDEX IF NOT EXISTS idx_storyline_processing_log_started_at ON storyline_processing_log(started_at);

-- Topic Clustering Indexes
CREATE INDEX IF NOT EXISTS idx_topic_clusters_type ON topic_clusters(cluster_type);
CREATE INDEX IF NOT EXISTS idx_topic_clusters_coherence ON topic_clusters(coherence_score);
CREATE INDEX IF NOT EXISTS idx_topic_clusters_article_count ON topic_clusters(article_count);
CREATE INDEX IF NOT EXISTS idx_topic_clusters_cluster_uuid ON topic_clusters(cluster_uuid);

CREATE INDEX IF NOT EXISTS idx_article_topic_clusters_article_id ON article_topic_clusters(article_id);
CREATE INDEX IF NOT EXISTS idx_article_topic_clusters_cluster_id ON article_topic_clusters(topic_cluster_id);
CREATE INDEX IF NOT EXISTS idx_article_topic_clusters_relevance ON article_topic_clusters(relevance_score);

CREATE INDEX IF NOT EXISTS idx_topic_keywords_cluster_id ON topic_keywords(topic_cluster_id);
CREATE INDEX IF NOT EXISTS idx_topic_keywords_frequency ON topic_keywords(frequency_count);
CREATE INDEX IF NOT EXISTS idx_topic_keywords_importance ON topic_keywords(importance_score);

-- Relationship Indexes
CREATE INDEX IF NOT EXISTS idx_storyline_articles_relevance ON storyline_articles(relevance_score);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_event_date ON storyline_articles(event_date);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_relationship_type ON storyline_articles(relationship_type);

-- System Monitoring Indexes
CREATE INDEX IF NOT EXISTS idx_system_metrics_type ON system_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_system_metrics_recorded_at ON system_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_system_metrics_tags_gin ON system_metrics USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_system_metrics_labels_gin ON system_metrics USING GIN (labels);

CREATE INDEX IF NOT EXISTS idx_system_alerts_alert_uuid ON system_alerts(alert_uuid);
CREATE INDEX IF NOT EXISTS idx_system_alerts_source_component ON system_alerts(source_component);
CREATE INDEX IF NOT EXISTS idx_system_alerts_triggered_at ON system_alerts(triggered_at);
CREATE INDEX IF NOT EXISTS idx_system_alerts_alert_data_gin ON system_alerts USING GIN (alert_data);

-- User Management Indexes
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_uuid ON user_profiles(user_uuid);
CREATE INDEX IF NOT EXISTS idx_user_profiles_is_active ON user_profiles(is_active);
CREATE INDEX IF NOT EXISTS idx_user_profiles_last_login ON user_profiles(last_login_at);
CREATE INDEX IF NOT EXISTS idx_user_profiles_preferences_gin ON user_profiles USING GIN (preferences);

-- Intelligence Hub Indexes
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_report_uuid ON intelligence_reports(report_uuid);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_status ON intelligence_reports(status);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_type ON intelligence_reports(analysis_type);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_generated_at ON intelligence_reports(generated_at);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_confidence ON intelligence_reports(confidence_score);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_content_gin ON intelligence_reports USING GIN (content);

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables with updated_at columns
DO $$
BEGIN
    -- Apply trigger to topic_clusters if it exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'topic_clusters') THEN
        DROP TRIGGER IF EXISTS trigger_topic_clusters_updated_at ON topic_clusters;
        CREATE TRIGGER trigger_topic_clusters_updated_at
            BEFORE UPDATE ON topic_clusters
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    -- Apply trigger to intelligence_reports if it exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'intelligence_reports') THEN
        DROP TRIGGER IF EXISTS trigger_intelligence_reports_updated_at ON intelligence_reports;
        CREATE TRIGGER trigger_intelligence_reports_updated_at
            BEFORE UPDATE ON intelligence_reports
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    RAISE NOTICE 'Triggers applied successfully';
END $$;

-- ============================================================================
-- INITIAL DATA: Processing Stages
-- ============================================================================

-- Insert default processing stages
INSERT INTO processing_stages (stage_name, stage_description, stage_order) VALUES
('ingestion', 'Article ingestion and basic validation', 1),
('content_analysis', 'Content structure and quality analysis', 2),
('sentiment_analysis', 'Sentiment and emotional analysis', 3),
('entity_extraction', 'Named entity recognition and extraction', 4),
('summarization', 'AI-powered content summarization', 5),
('topic_clustering', 'Topic identification and clustering', 6),
('quality_assessment', 'Overall quality and credibility scoring', 7),
('completed', 'Processing pipeline completed', 8)
ON CONFLICT (stage_name) DO NOTHING;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Articles with Processing Status
CREATE OR REPLACE VIEW articles_with_processing_status AS
SELECT 
    a.*,
    rss.name as feed_name,
    COUNT(apc.topic_cluster_id) as topic_cluster_count,
    COUNT(sa.storyline_id) as storyline_count
FROM articles a
LEFT JOIN rss_feeds rss ON a.feed_id = rss.id
LEFT JOIN article_topic_clusters apc ON a.id = apc.article_id
LEFT JOIN storyline_articles sa ON a.id = sa.article_id
GROUP BY a.id, rss.name;

-- Storylines with Statistics
CREATE OR REPLACE VIEW storylines_with_statistics AS
SELECT 
    s.*,
    COUNT(sa.article_id) as total_articles,
    COUNT(DISTINCT sa.article_id) as unique_articles,
    MIN(sa.event_date) as earliest_event,
    MAX(sa.event_date) as latest_event
FROM storylines s
LEFT JOIN storyline_articles sa ON s.id = sa.storyline_id
GROUP BY s.id;

-- Topic Clusters with Statistics
CREATE OR REPLACE VIEW topic_clusters_with_statistics AS
SELECT 
    tc.*,
    COUNT(atc.article_id) as article_count,
    COUNT(tk.keyword) as keyword_count,
    AVG(atc.relevance_score) as avg_relevance_score
FROM topic_clusters tc
LEFT JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
LEFT JOIN topic_keywords tk ON tc.id = tk.topic_cluster_id
GROUP BY tc.id;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'v4.0 Schema Enhancement Migration Completed Successfully';
    RAISE NOTICE 'Enhanced existing tables with consistent naming and robust metadata';
    RAISE NOTICE 'Created new pipeline processing tables';
    RAISE NOTICE 'Created topic clustering system for word cloud functionality';
    RAISE NOTICE 'Added performance-optimized indexes';
    RAISE NOTICE 'Created helpful views for common queries';
    RAISE NOTICE 'Schema is now ready for scalable pipeline processing with robust metadata tracking';
END $$;
