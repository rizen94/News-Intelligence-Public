-- News Intelligence System v3.0 - Base Database Schema
-- This script creates the core tables needed for the system to function
-- Run this first before other schema updates

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Articles table - Core content storage
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    url TEXT,
    source VARCHAR(255),
    published_date TIMESTAMP,
    category VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en',
    quality_score DECIMAL(3,2) DEFAULT 0.0,
    processing_status VARCHAR(50) DEFAULT 'raw',
    content_hash VARCHAR(64),
    deduplication_status VARCHAR(50) DEFAULT 'pending',
    content_similarity_score DECIMAL(3,2),
    normalized_content TEXT,
    ml_data JSONB,
    rag_keep_longer BOOLEAN DEFAULT FALSE,
    rag_context_needed BOOLEAN DEFAULT FALSE,
    rag_priority INTEGER DEFAULT 0,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RSS Feeds table - Source management
CREATE TABLE IF NOT EXISTS rss_feeds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL UNIQUE,
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    last_check TIMESTAMP,
    last_success TIMESTAMP,
    failure_count INTEGER DEFAULT 0,
    article_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Entities table - Named entity recognition
CREATE TABLE IF NOT EXISTS entities (
    id SERIAL PRIMARY KEY,
    text VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- PERSON, ORG, GPE, LOCATION, etc.
    frequency INTEGER DEFAULT 1,
    confidence DECIMAL(3,2) DEFAULT 0.0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Article Clusters table - Story clustering
CREATE TABLE IF NOT EXISTS article_clusters (
    id SERIAL PRIMARY KEY,
    main_article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    cluster_type VARCHAR(50) DEFAULT 'story',
    topic TEXT,
    summary TEXT,
    article_count INTEGER DEFAULT 1,
    cohesion_score DECIMAL(3,2) DEFAULT 0.0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cluster Articles mapping table
CREATE TABLE IF NOT EXISTS cluster_articles (
    id SERIAL PRIMARY KEY,
    cluster_id INTEGER REFERENCES article_clusters(id) ON DELETE CASCADE,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    similarity_score DECIMAL(3,2),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cluster_id, article_id)
);

-- ============================================================================
-- CONTENT PRIORITIZATION TABLES
-- ============================================================================

-- Priority Levels table
CREATE TABLE IF NOT EXISTS content_priority_levels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    color VARCHAR(7) DEFAULT '#2196f3',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Story Threads table
CREATE TABLE IF NOT EXISTS story_threads (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Content Priority Assignments table
CREATE TABLE IF NOT EXISTS content_priority_assignments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    thread_id INTEGER REFERENCES story_threads(id) ON DELETE CASCADE,
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by VARCHAR(100),
    notes TEXT,
    UNIQUE(article_id, thread_id)
);

-- User Rules table
CREATE TABLE IF NOT EXISTS user_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- 'keyword', 'source_filter', 'category_filter'
    rule_config JSONB NOT NULL,
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Collection Rules table
CREATE TABLE IF NOT EXISTS collection_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- 'source', 'category', 'keyword'
    rule_config JSONB NOT NULL,
    feed_id INTEGER REFERENCES rss_feeds(id) ON DELETE CASCADE,
    max_articles_per_collection INTEGER DEFAULT 50,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- DEDUPLICATION TABLES
-- ============================================================================

-- Content Hashes table for deduplication
CREATE TABLE IF NOT EXISTS content_hashes (
    id SERIAL PRIMARY KEY,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    hash_type VARCHAR(20) DEFAULT 'sha256',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Similarity Scores table
CREATE TABLE IF NOT EXISTS similarity_scores (
    id SERIAL PRIMARY KEY,
    article_id_1 INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    article_id_2 INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    similarity_score DECIMAL(3,2) NOT NULL,
    comparison_method VARCHAR(50),
    compared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id_1, article_id_2)
);

-- ============================================================================
-- MONITORING TABLES
-- ============================================================================

-- System Logs table
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL, -- 'info', 'warning', 'error', 'critical'
    message TEXT NOT NULL,
    source VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Metrics table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,2),
    metric_unit VARCHAR(20),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Articles indexes
CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles(published_date);
CREATE INDEX IF NOT EXISTS idx_articles_processing_status ON articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);

-- RSS Feeds indexes
CREATE INDEX IF NOT EXISTS idx_rss_feeds_url ON rss_feeds(url);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_category ON rss_feeds(category);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_is_active ON rss_feeds(is_active);

-- Entities indexes
CREATE INDEX IF NOT EXISTS idx_entities_text ON entities(text);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_frequency ON entities(frequency);

-- Clusters indexes
CREATE INDEX IF NOT EXISTS idx_article_clusters_main_article ON article_clusters(main_article_id);
CREATE INDEX IF NOT EXISTS idx_article_clusters_type ON article_clusters(cluster_type);
CREATE INDEX IF NOT EXISTS idx_article_clusters_created_date ON article_clusters(created_date);

-- Priority indexes
CREATE INDEX IF NOT EXISTS idx_content_priority_assignments_article ON content_priority_assignments(article_id);
CREATE INDEX IF NOT EXISTS idx_content_priority_assignments_thread ON content_priority_assignments(thread_id);
CREATE INDEX IF NOT EXISTS idx_story_threads_priority ON story_threads(priority_level_id);
CREATE INDEX IF NOT EXISTS idx_story_threads_status ON story_threads(status);

-- Monitoring indexes
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_name ON performance_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp);

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert default priority levels
INSERT INTO content_priority_levels (name, description, color, sort_order) VALUES
('Critical', 'Highest priority - immediate attention required', '#f44336', 1),
('High', 'High priority - important content', '#ff9800', 2),
('Medium', 'Medium priority - standard content', '#2196f3', 3),
('Low', 'Low priority - background information', '#4caf50', 4)
ON CONFLICT (name) DO NOTHING;

-- Insert sample RSS feeds
INSERT INTO rss_feeds (name, url, category, is_active) VALUES
('BBC News', 'https://feeds.bbci.co.uk/news/rss.xml', 'General', true),
('Reuters', 'https://feeds.reuters.com/reuters/topNews', 'General', true),
('TechCrunch', 'https://techcrunch.com/feed/', 'Technology', true),
('The Verge', 'https://www.theverge.com/rss/index.xml', 'Technology', true)
ON CONFLICT (url) DO NOTHING;

-- ============================================================================
-- GRANTS AND PERMISSIONS
-- ============================================================================

-- Grant permissions to the NewsInt_DB user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "NewsInt_DB";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "NewsInt_DB";
GRANT ALL PRIVILEGES ON SCHEMA public TO "NewsInt_DB";

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Base schema created successfully for News Intelligence System v3.0';
    RAISE NOTICE 'Tables created: articles, rss_feeds, entities, article_clusters, content_priority_levels, story_threads, content_priority_assignments, user_rules, collection_rules, content_hashes, similarity_scores, system_logs, performance_metrics';
    RAISE NOTICE 'Indexes created for optimal performance';
    RAISE NOTICE 'Initial data inserted: priority levels and sample RSS feeds';
END $$;
