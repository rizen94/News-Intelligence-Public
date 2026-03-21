-- Migration 100: Complete v4.0 Schema Overhaul
-- Comprehensive database redesign for News Intelligence System v4.0
-- Addresses: naming consistency, pipeline processing, metadata tracking, topic clustering
-- Created: October 22, 2025
-- Version: 4.0.0

-- ============================================================================
-- SCHEMA OVERHAUL: Consistent Naming, Robust Metadata, Pipeline Processing
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================================
-- CORE ENTITIES: RSS Feeds, Articles, Storylines
-- ============================================================================

-- RSS Feeds Table (Enhanced with consistent naming)
CREATE TABLE IF NOT EXISTS rss_feeds (
    id SERIAL PRIMARY KEY,
    feed_name VARCHAR(200) NOT NULL,
    feed_url VARCHAR(1000) NOT NULL,
    feed_description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    fetch_interval_seconds INTEGER NOT NULL DEFAULT 300,
    last_fetched_at TIMESTAMP WITH TIME ZONE,
    last_successful_fetch_at TIMESTAMP WITH TIME ZONE,
    error_count INTEGER NOT NULL DEFAULT 0,
    last_error_message TEXT,
    success_rate DECIMAL(5,2) DEFAULT 100.0,
    average_response_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    tags JSONB DEFAULT '[]',
    quality_score DECIMAL(3,2) DEFAULT 0.0,
    
    -- Constraints
    CONSTRAINT chk_fetch_interval CHECK (fetch_interval_seconds >= 60),
    CONSTRAINT chk_success_rate CHECK (success_rate >= 0.0 AND success_rate <= 100.0),
    CONSTRAINT chk_quality_score CHECK (quality_score >= 0.0 AND quality_score <= 1.0)
);

-- Articles Table (Complete overhaul with pipeline processing)
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    article_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Basic Content
    title VARCHAR(500) NOT NULL,
    content TEXT,
    excerpt TEXT,
    url VARCHAR(1000),
    canonical_url VARCHAR(1000),
    
    -- Publishing Information
    published_at TIMESTAMP WITH TIME ZONE,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    author VARCHAR(255),
    publisher VARCHAR(255),
    source_domain VARCHAR(255),
    
    -- Content Analysis
    language_code VARCHAR(10) DEFAULT 'en',
    word_count INTEGER DEFAULT 0,
    reading_time_minutes INTEGER DEFAULT 0,
    content_hash VARCHAR(64),
    
    -- Processing Pipeline State
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (processing_status IN (
        'pending', 'ingesting', 'analyzing', 'summarizing', 'clustering', 
        'completed', 'failed', 'archived'
    )),
    processing_stage VARCHAR(50) DEFAULT 'ingestion' CHECK (processing_stage IN (
        'ingestion', 'content_analysis', 'sentiment_analysis', 'entity_extraction',
        'summarization', 'topic_clustering', 'quality_assessment', 'completed'
    )),
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    processing_error_message TEXT,
    
    -- Quality Metrics
    quality_score DECIMAL(3,2) DEFAULT 0.0,
    readability_score DECIMAL(3,2) DEFAULT 0.0,
    bias_score DECIMAL(3,2) DEFAULT 0.0,
    credibility_score DECIMAL(3,2) DEFAULT 0.0,
    
    -- AI Analysis Results
    summary TEXT,
    sentiment_label VARCHAR(20),
    sentiment_score DECIMAL(3,2),
    sentiment_confidence DECIMAL(3,2),
    
    -- Structured Data (All JSONB for consistency)
    entities JSONB DEFAULT '{}',
    topics JSONB DEFAULT '[]',
    keywords JSONB DEFAULT '[]',
    categories JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    analysis_results JSONB DEFAULT '{}',
    
    -- Relationships
    rss_feed_id INTEGER REFERENCES rss_feeds(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_quality_scores CHECK (
        quality_score >= 0.0 AND quality_score <= 1.0 AND
        readability_score >= 0.0 AND readability_score <= 1.0 AND
        bias_score >= 0.0 AND bias_score <= 1.0 AND
        credibility_score >= 0.0 AND credibility_score <= 1.0
    ),
    CONSTRAINT chk_sentiment_scores CHECK (
        sentiment_score >= -1.0 AND sentiment_score <= 1.0 AND
        sentiment_confidence >= 0.0 AND sentiment_confidence <= 1.0
    )
);

-- Storylines Table (Enhanced with comprehensive tracking)
CREATE TABLE IF NOT EXISTS storylines (
    id SERIAL PRIMARY KEY,
    storyline_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Basic Information
    title VARCHAR(300) NOT NULL,
    description TEXT,
    summary TEXT,
    
    -- Status and Processing
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN (
        'draft', 'active', 'archived', 'completed', 'failed'
    )),
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (processing_status IN (
        'pending', 'analyzing', 'timeline_generation', 'rag_analysis', 
        'completed', 'failed'
    )),
    
    -- Quality Metrics
    quality_score DECIMAL(3,2) DEFAULT 0.0,
    completeness_score DECIMAL(3,2) DEFAULT 0.0,
    coherence_score DECIMAL(3,2) DEFAULT 0.0,
    
    -- Content Analysis
    total_articles INTEGER DEFAULT 0,
    total_entities INTEGER DEFAULT 0,
    total_events INTEGER DEFAULT 0,
    time_span_days INTEGER DEFAULT 0,
    
    -- Structured Data
    key_entities JSONB DEFAULT '{}',
    timeline_events JSONB DEFAULT '[]',
    topic_clusters JSONB DEFAULT '[]',
    sentiment_trends JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    analysis_results JSONB DEFAULT '{}',
    
    -- Processing Metadata
    last_analysis_at TIMESTAMP WITH TIME ZONE,
    analysis_version INTEGER DEFAULT 1,
    processing_errors JSONB DEFAULT '[]',
    
    -- Relationships
    created_by VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_storyline_scores CHECK (
        quality_score >= 0.0 AND quality_score <= 1.0 AND
        completeness_score >= 0.0 AND completeness_score <= 1.0 AND
        coherence_score >= 0.0 AND coherence_score <= 1.0
    )
);

-- ============================================================================
-- PIPELINE PROCESSING TABLES
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
-- RELATIONSHIP TABLES
-- ============================================================================

-- Storyline-Article Relationships
CREATE TABLE IF NOT EXISTS storyline_articles (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    
    -- Relationship Metadata
    relevance_score DECIMAL(3,2) DEFAULT 0.0,
    confidence_score DECIMAL(3,2) DEFAULT 0.0,
    relationship_type VARCHAR(50) DEFAULT 'related' CHECK (relationship_type IN (
        'related', 'core', 'supporting', 'context', 'background'
    )),
    
    -- Temporal Information
    event_date DATE,
    chronological_order INTEGER,
    
    -- Metadata
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    added_by VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_relationship_scores CHECK (
        relevance_score >= 0.0 AND relevance_score <= 1.0 AND
        confidence_score >= 0.0 AND confidence_score <= 1.0
    ),
    UNIQUE(storyline_id, article_id)
);

-- ============================================================================
-- SYSTEM MONITORING TABLES
-- ============================================================================

-- System Metrics
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(50),
    metric_type VARCHAR(50) DEFAULT 'gauge' CHECK (metric_type IN (
        'gauge', 'counter', 'histogram', 'summary'
    )),
    
    -- Context
    tags JSONB DEFAULT '{}',
    labels JSONB DEFAULT '{}',
    
    -- Timestamps
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_metric_value CHECK (metric_value >= 0.0)
);

-- System Alerts
CREATE TABLE IF NOT EXISTS system_alerts (
    id SERIAL PRIMARY KEY,
    alert_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Alert Information
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN (
        'low', 'medium', 'high', 'critical'
    )),
    title VARCHAR(300) NOT NULL,
    description TEXT,
    message TEXT,
    
    -- Alert State
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN (
        'active', 'acknowledged', 'resolved', 'suppressed'
    )),
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Context
    source_component VARCHAR(100),
    alert_data JSONB DEFAULT '{}',
    resolution_data JSONB DEFAULT '{}',
    
    -- Timestamps
    triggered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- USER MANAGEMENT TABLES
-- ============================================================================

-- User Profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Basic Information
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    
    -- Preferences
    preferences JSONB DEFAULT '{}',
    notification_settings JSONB DEFAULT '{}',
    
    -- Metadata
    roles JSONB DEFAULT '["user"]',
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INTELLIGENCE HUB TABLES
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
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- RSS Feeds Indexes
CREATE INDEX IF NOT EXISTS idx_rss_feeds_active ON rss_feeds(is_active);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_last_fetched ON rss_feeds(last_fetched_at);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_quality ON rss_feeds(quality_score);

-- Articles Indexes
CREATE INDEX IF NOT EXISTS idx_articles_processing_status ON articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_articles_processing_stage ON articles(processing_stage);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_source_domain ON articles(source_domain);
CREATE INDEX IF NOT EXISTS idx_articles_quality_score ON articles(quality_score);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_rss_feed_id ON articles(rss_feed_id);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);

-- GIN Indexes for JSONB columns
CREATE INDEX IF NOT EXISTS idx_articles_entities_gin ON articles USING GIN (entities);
CREATE INDEX IF NOT EXISTS idx_articles_topics_gin ON articles USING GIN (topics);
CREATE INDEX IF NOT EXISTS idx_articles_keywords_gin ON articles USING GIN (keywords);
CREATE INDEX IF NOT EXISTS idx_articles_tags_gin ON articles USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_articles_metadata_gin ON articles USING GIN (metadata);

-- Storylines Indexes
CREATE INDEX IF NOT EXISTS idx_storylines_status ON storylines(status);
CREATE INDEX IF NOT EXISTS idx_storylines_processing_status ON storylines(processing_status);
CREATE INDEX IF NOT EXISTS idx_storylines_quality_score ON storylines(quality_score);
CREATE INDEX IF NOT EXISTS idx_storylines_created_at ON storylines(created_at);
CREATE INDEX IF NOT EXISTS idx_storylines_updated_at ON storylines(updated_at);

-- GIN Indexes for Storylines JSONB
CREATE INDEX IF NOT EXISTS idx_storylines_key_entities_gin ON storylines USING GIN (key_entities);
CREATE INDEX IF NOT EXISTS idx_storylines_timeline_events_gin ON storylines USING GIN (timeline_events);
CREATE INDEX IF NOT EXISTS idx_storylines_topic_clusters_gin ON storylines USING GIN (topic_clusters);

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

CREATE INDEX IF NOT EXISTS idx_article_topic_clusters_article_id ON article_topic_clusters(article_id);
CREATE INDEX IF NOT EXISTS idx_article_topic_clusters_cluster_id ON article_topic_clusters(topic_cluster_id);
CREATE INDEX IF NOT EXISTS idx_article_topic_clusters_relevance ON article_topic_clusters(relevance_score);

CREATE INDEX IF NOT EXISTS idx_topic_keywords_cluster_id ON topic_keywords(topic_cluster_id);
CREATE INDEX IF NOT EXISTS idx_topic_keywords_frequency ON topic_keywords(frequency_count);
CREATE INDEX IF NOT EXISTS idx_topic_keywords_importance ON topic_keywords(importance_score);

-- Relationship Indexes
CREATE INDEX IF NOT EXISTS idx_storyline_articles_storyline_id ON storyline_articles(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_article_id ON storyline_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_relevance ON storyline_articles(relevance_score);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_event_date ON storyline_articles(event_date);

-- System Monitoring Indexes
CREATE INDEX IF NOT EXISTS idx_system_metrics_name ON system_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_system_metrics_recorded_at ON system_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_system_metrics_tags_gin ON system_metrics USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_system_alerts_type ON system_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_system_alerts_severity ON system_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_system_alerts_status ON system_alerts(status);
CREATE INDEX IF NOT EXISTS idx_system_alerts_triggered_at ON system_alerts(triggered_at);
CREATE INDEX IF NOT EXISTS idx_system_alerts_is_active ON system_alerts(is_active);

-- User Management Indexes
CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles(username);
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_is_active ON user_profiles(is_active);
CREATE INDEX IF NOT EXISTS idx_user_profiles_last_login ON user_profiles(last_login_at);

-- Intelligence Hub Indexes
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_status ON intelligence_reports(status);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_type ON intelligence_reports(analysis_type);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_generated_at ON intelligence_reports(generated_at);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_confidence ON intelligence_reports(confidence_score);

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

-- Apply triggers to all tables with updated_at columns
CREATE TRIGGER trigger_rss_feeds_updated_at
    BEFORE UPDATE ON rss_feeds
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_storylines_updated_at
    BEFORE UPDATE ON storylines
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_topic_clusters_updated_at
    BEFORE UPDATE ON topic_clusters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_system_alerts_updated_at
    BEFORE UPDATE ON system_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_intelligence_reports_updated_at
    BEFORE UPDATE ON intelligence_reports
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

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
    rss.feed_name,
    COUNT(apc.topic_cluster_id) as topic_cluster_count,
    COUNT(sa.storyline_id) as storyline_count
FROM articles a
LEFT JOIN rss_feeds rss ON a.rss_feed_id = rss.id
LEFT JOIN article_topic_clusters apc ON a.id = apc.article_id
LEFT JOIN storyline_articles sa ON a.id = sa.article_id
GROUP BY a.id, rss.feed_name;

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
    RAISE NOTICE 'v4.0 Complete Schema Overhaul Migration Completed Successfully';
    RAISE NOTICE 'Created Tables: rss_feeds, articles, storylines, processing_stages, article_processing_log, storyline_processing_log';
    RAISE NOTICE 'Created Topic Clustering Tables: topic_clusters, article_topic_clusters, topic_keywords';
    RAISE NOTICE 'Created Relationship Tables: storyline_articles';
    RAISE NOTICE 'Created System Tables: system_metrics, system_alerts, user_profiles, intelligence_reports';
    RAISE NOTICE 'Created Indexes: Performance-optimized indexes for all tables';
    RAISE NOTICE 'Created Triggers: Automatic updated_at timestamp updates';
    RAISE NOTICE 'Created Views: Common query optimization views';
    RAISE NOTICE 'Schema is now ready for scalable pipeline processing with robust metadata tracking';
END $$;
