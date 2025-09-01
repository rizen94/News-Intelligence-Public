-- News Intelligence System v2.1.0 - Complete Database Schema Update
-- This script updates the database to fully support the intelligence system pipeline
-- Includes status tracking, data separation, and RAG system support

-- ============================================================================
-- 1. UPDATE EXISTING ARTICLES TABLE
-- ============================================================================

-- Add processing_status column with proper constraints
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'processing_status'
    ) THEN
        ALTER TABLE articles ADD COLUMN processing_status VARCHAR(50) DEFAULT 'raw';
        RAISE NOTICE 'Added processing_status column to articles table';
    ELSE
        RAISE NOTICE 'processing_status column already exists in articles table';
    END IF;
END $$;

-- Add ML data column for processed content
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_data'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_data JSONB;
        RAISE NOTICE 'Added ml_data column to articles table';
    ELSE
        RAISE NOTICE 'ml_data column already exists in articles table';
    END IF;
END $$;

-- Add RAG system flags
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'rag_keep_longer'
    ) THEN
        ALTER TABLE articles ADD COLUMN rag_keep_longer BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added rag_keep_longer column to articles table';
    ELSE
        RAISE NOTICE 'rag_keep_longer column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'rag_context_needed'
    ) THEN
        ALTER TABLE articles ADD COLUMN rag_context_needed BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added rag_context_needed column to articles table';
    ELSE
        RAISE NOTICE 'rag_context_needed column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'rag_priority'
    ) THEN
        ALTER TABLE articles ADD COLUMN rag_priority INTEGER DEFAULT 0;
        RAISE NOTICE 'Added rag_priority column to articles table';
    ELSE
        RAISE NOTICE 'rag_priority column already exists in articles table';
    END IF;
END $$;

-- Add processing timestamps
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'processing_started_at'
    ) THEN
        ALTER TABLE articles ADD COLUMN processing_started_at TIMESTAMP;
        RAISE NOTICE 'Added processing_started_at column to articles table';
    ELSE
        RAISE NOTICE 'processing_started_at column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'processing_completed_at'
    ) THEN
        ALTER TABLE articles ADD COLUMN processing_completed_at TIMESTAMP;
        RAISE NOTICE 'Added processing_completed_at column to articles table';
    ELSE
        RAISE NOTICE 'processing_completed_at column already exists in articles table';
    END IF;
END $$;

-- ============================================================================
-- 2. CREATE PROCESSED ARTICLES TABLE (SEPARATE FROM RAW)
-- ============================================================================

CREATE TABLE IF NOT EXISTS processed_articles (
    processed_id SERIAL PRIMARY KEY,
    original_article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    
    -- Processed content
    cleaned_title TEXT NOT NULL,
    cleaned_content TEXT NOT NULL,
    content_segments JSONB, -- Array of content segments for ML processing
    
    -- ML processing results
    key_phrases TEXT[],
    quality_score DECIMAL(5,2),
    content_metrics JSONB, -- word_count, char_count, reading_time, etc.
    
    -- Processing metadata
    processing_version VARCHAR(20) DEFAULT '2.1.0',
    processing_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 3. CREATE RAG SYSTEM TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS rag_context_requests (
    request_id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    
    -- RAG request details
    context_type VARCHAR(50) NOT NULL, -- 'background', 'related_stories', 'expert_analysis'
    context_description TEXT,
    priority INTEGER DEFAULT 1,
    
    -- Request status
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'in_progress', 'completed', 'failed'
    
    -- RAG processing results
    context_data JSONB,
    sources_used TEXT[],
    confidence_score DECIMAL(5,2),
    
    -- Timestamps
    requested_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag_research_topics (
    topic_id SERIAL PRIMARY KEY,
    topic_name VARCHAR(255) NOT NULL UNIQUE,
    topic_description TEXT,
    
    -- Topic tracking
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 1,
    
    -- Research parameters
    research_frequency VARCHAR(50) DEFAULT 'daily', -- 'hourly', 'daily', 'weekly'
    max_context_age_days INTEGER DEFAULT 30,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_researched_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rag_research_sessions (
    session_id SERIAL PRIMARY KEY,
    topic_id INTEGER REFERENCES rag_research_topics(topic_id),
    
    -- Session details
    session_type VARCHAR(50) NOT NULL, -- 'scheduled', 'manual', 'triggered'
    trigger_article_id INTEGER REFERENCES articles(id),
    
    -- Research scope
    articles_researched INTEGER DEFAULT 0,
    context_generated INTEGER DEFAULT 0,
    
    -- Session status
    status VARCHAR(50) DEFAULT 'running', -- 'running', 'completed', 'failed'
    
    -- Results
    session_results JSONB,
    errors TEXT[],
    
    -- Timestamps
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 4. CREATE INTELLIGENCE PROCESSING TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS article_clusters (
    cluster_id SERIAL PRIMARY KEY,
    main_article_id INTEGER REFERENCES articles(id),
    article_ids INTEGER[] NOT NULL,
    
    -- Cluster metadata
    cluster_type VARCHAR(50), -- 'topic', 'event', 'timeline', 'source'
    cluster_summary TEXT,
    cluster_keywords TEXT[],
    
    -- ML processing data
    similarity_scores JSONB,
    cluster_quality_score DECIMAL(5,2),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ml_datasets (
    dataset_id SERIAL PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL UNIQUE,
    dataset_description TEXT,
    
    -- Dataset configuration
    filters JSONB,
    target_article_count INTEGER,
    actual_article_count INTEGER DEFAULT 0,
    
    -- Dataset status
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'archived', 'processing'
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ml_dataset_content (
    content_id SERIAL PRIMARY KEY,
    dataset_id INTEGER REFERENCES ml_datasets(dataset_id) ON DELETE CASCADE,
    
    -- Content data
    content JSONB NOT NULL,
    content_hash VARCHAR(64) UNIQUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence_pipeline_results (
    result_id SERIAL PRIMARY KEY,
    
    -- Pipeline execution
    pipeline_version VARCHAR(20) DEFAULT '2.1.0',
    pipeline_type VARCHAR(50) NOT NULL, -- 'full', 'incremental', 'single_article'
    
    -- Execution details
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_minutes DECIMAL(10,2),
    
    -- Processing results
    articles_processed INTEGER DEFAULT 0,
    articles_successful INTEGER DEFAULT 0,
    articles_failed INTEGER DEFAULT 0,
    clusters_created INTEGER DEFAULT 0,
    datasets_created INTEGER DEFAULT 0,
    
    -- Execution details
    steps_completed TEXT[],
    errors TEXT[],
    warnings TEXT[],
    results_data JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 5. CREATE CLEANUP PROTECTION SYSTEM
-- ============================================================================

CREATE TABLE IF NOT EXISTS cleanup_protection_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL UNIQUE,
    rule_description TEXT,
    
    -- Protection criteria
    protection_type VARCHAR(50) NOT NULL, -- 'rag_keep_longer', 'high_priority', 'research_topic'
    criteria JSONB NOT NULL, -- JSON conditions for protection
    
    -- Protection settings
    min_retention_days INTEGER DEFAULT 90,
    max_retention_days INTEGER DEFAULT 365,
    cleanup_priority INTEGER DEFAULT 1,
    
    -- Rule status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 6. CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Articles table indexes
CREATE INDEX IF NOT EXISTS idx_articles_processing_status ON articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_articles_rag_keep_longer ON articles(rag_keep_longer);
CREATE INDEX IF NOT EXISTS idx_articles_rag_priority ON articles(rag_priority);
CREATE INDEX IF NOT EXISTS idx_articles_processing_started_at ON articles(processing_started_at);
CREATE INDEX IF NOT EXISTS idx_articles_processing_completed_at ON articles(processing_completed_at);
CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles(published_date);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);
CREATE INDEX IF NOT EXISTS idx_articles_updated_at ON articles(updated_at);

-- Processed articles indexes
CREATE INDEX IF NOT EXISTS idx_processed_articles_original_id ON processed_articles(original_article_id);
CREATE INDEX IF NOT EXISTS idx_processed_articles_quality_score ON processed_articles(quality_score);
CREATE INDEX IF NOT EXISTS idx_processed_articles_created_at ON processed_articles(created_at);

-- RAG system indexes
CREATE INDEX IF NOT EXISTS idx_rag_context_requests_article_id ON rag_context_requests(article_id);
CREATE INDEX IF NOT EXISTS idx_rag_context_requests_status ON rag_context_requests(status);
CREATE INDEX IF NOT EXISTS idx_rag_context_requests_priority ON rag_context_requests(priority);
CREATE INDEX IF NOT EXISTS idx_rag_research_topics_active ON rag_research_topics(is_active);
CREATE INDEX IF NOT EXISTS idx_rag_research_sessions_topic_id ON rag_research_sessions(topic_id);
CREATE INDEX IF NOT EXISTS idx_rag_research_sessions_status ON rag_research_sessions(status);

-- Intelligence system indexes
CREATE INDEX IF NOT EXISTS idx_article_clusters_main_article ON article_clusters(main_article_id);
CREATE INDEX IF NOT EXISTS idx_article_clusters_type ON article_clusters(cluster_type);
CREATE INDEX IF NOT EXISTS idx_ml_datasets_name ON ml_datasets(dataset_name);
CREATE INDEX IF NOT EXISTS idx_ml_datasets_status ON ml_datasets(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_type ON intelligence_pipeline_results(pipeline_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_started_at ON intelligence_pipeline_results(started_at);

-- ============================================================================
-- 7. CREATE FUNCTIONS FOR INTELLIGENCE SYSTEM
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to get comprehensive ML processing statistics
CREATE OR REPLACE FUNCTION get_ml_processing_stats()
RETURNS TABLE(
    total_articles BIGINT,
    raw_articles BIGINT,
    processing_articles BIGINT,
    ml_processed BIGINT,
    processing_errors BIGINT,
    processing_progress DECIMAL(5,2),
    clusters_count BIGINT,
    datasets_count BIGINT,
    rag_requests_pending BIGINT,
    rag_requests_completed BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_articles,
        COUNT(CASE WHEN processing_status = 'raw' THEN 1 END)::BIGINT as raw_articles,
        COUNT(CASE WHEN processing_status IN ('processing', 'in_process') THEN 1 END)::BIGINT as processing_articles,
        COUNT(CASE WHEN processing_status = 'ml_processed' THEN 1 END)::BIGINT as ml_processed,
        COUNT(CASE WHEN processing_status = 'processing_error' THEN 1 END)::BIGINT as processing_errors,
        CASE 
            WHEN COUNT(*) > 0 THEN 
                ROUND((COUNT(CASE WHEN processing_status = 'ml_processed' THEN 1 END)::DECIMAL / COUNT(*)) * 100, 2)
            ELSE 0 
        END as processing_progress,
        (SELECT COUNT(*) FROM article_clusters)::BIGINT as clusters_count,
        (SELECT COUNT(*) FROM ml_datasets)::BIGINT as datasets_count,
        (SELECT COUNT(*) FROM rag_context_requests WHERE status = 'pending')::BIGINT as rag_requests_pending,
        (SELECT COUNT(*) FROM rag_context_requests WHERE status = 'completed')::BIGINT as rag_requests_completed
    FROM articles;
END;
$$ LANGUAGE plpgsql;

-- Function to get articles that need RAG context
CREATE OR REPLACE FUNCTION get_articles_needing_rag_context()
RETURNS TABLE(
    article_id INTEGER,
    title TEXT,
    rag_priority INTEGER,
    context_needed BOOLEAN,
    days_since_publication INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.title,
        a.rag_priority,
        a.rag_context_needed,
        EXTRACT(DAY FROM NOW() - a.published_date)::INTEGER as days_since_publication
    FROM articles a
    WHERE a.rag_context_needed = TRUE 
       OR a.rag_keep_longer = TRUE
       OR a.rag_priority > 0
    ORDER BY a.rag_priority DESC, a.published_date DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get cleanup protection status for articles
CREATE OR REPLACE FUNCTION get_cleanup_protection_status(article_id_param INTEGER)
RETURNS TABLE(
    is_protected BOOLEAN,
    protection_reason TEXT,
    min_retention_days INTEGER,
    max_retention_days INTEGER,
    recommended_action TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        CASE 
            WHEN a.rag_keep_longer = TRUE OR a.rag_context_needed = TRUE OR a.rag_priority > 0
            THEN TRUE
            ELSE FALSE
        END as is_protected,
        CASE 
            WHEN a.rag_keep_longer = TRUE THEN 'RAG system marked for longer retention'
            WHEN a.rag_context_needed = TRUE THEN 'RAG context research needed'
            WHEN a.rag_priority > 0 THEN 'High priority article'
            ELSE 'No protection rules apply'
        END as protection_reason,
        CASE 
            WHEN a.rag_keep_longer = TRUE THEN 90
            WHEN a.rag_context_needed = TRUE THEN 60
            WHEN a.rag_priority > 0 THEN 30
            ELSE 7
        END as min_retention_days,
        CASE 
            WHEN a.rag_keep_longer = TRUE THEN 365
            WHEN a.rag_context_needed = TRUE THEN 180
            WHEN a.rag_priority > 0 THEN 90
            ELSE 30
        END as max_retention_days,
        CASE 
            WHEN a.rag_keep_longer = TRUE THEN 'Keep for extended research'
            WHEN a.rag_context_needed = TRUE THEN 'Research context before cleanup'
            WHEN a.rag_priority > 0 THEN 'Monitor for updates'
            ELSE 'Safe to cleanup'
        END as recommended_action
    FROM articles a
    WHERE a.id = article_id_param;
END;
$$ LANGUAGE plpgsql;

-- Function to mark articles for RAG processing
CREATE OR REPLACE FUNCTION mark_article_for_rag(
    article_id_param INTEGER,
    context_needed BOOLEAN DEFAULT TRUE,
    keep_longer BOOLEAN DEFAULT FALSE,
    priority INTEGER DEFAULT 1
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE articles 
    SET 
        rag_context_needed = context_needed,
        rag_keep_longer = keep_longer,
        rag_priority = priority,
        updated_at = NOW()
    WHERE id = article_id_param;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. CREATE TRIGGERS
-- ============================================================================

-- Trigger for processed_articles table
DROP TRIGGER IF EXISTS update_processed_articles_updated_at ON processed_articles;
CREATE TRIGGER update_processed_articles_updated_at
    BEFORE UPDATE ON processed_articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for article_clusters table
DROP TRIGGER IF EXISTS update_article_clusters_updated_at ON article_clusters;
CREATE TRIGGER update_article_clusters_updated_at
    BEFORE UPDATE ON article_clusters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for ml_datasets table
DROP TRIGGER IF EXISTS update_ml_datasets_updated_at ON ml_datasets;
CREATE TRIGGER update_ml_datasets_updated_at
    BEFORE UPDATE ON ml_datasets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for rag_research_topics table
DROP TRIGGER IF EXISTS update_rag_research_topics_updated_at ON rag_research_topics;
CREATE TRIGGER update_rag_research_topics_updated_at
    BEFORE UPDATE ON rag_research_topics
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 9. INSERT DEFAULT DATA
-- ============================================================================

-- Insert default cleanup protection rules
INSERT INTO cleanup_protection_rules (rule_name, rule_description, protection_type, criteria, min_retention_days, max_retention_days) VALUES
('RAG Keep Longer', 'Protects articles marked by RAG system for extended retention', 'rag_keep_longer', '{"rag_keep_longer": true}', 90, 365),
('RAG Context Needed', 'Protects articles that need RAG context research', 'rag_context_needed', '{"rag_context_needed": true}', 60, 180),
('High Priority Articles', 'Protects high priority articles from cleanup', 'high_priority', '{"rag_priority": {"gt": 0}}', 30, 90),
('Research Topics', 'Protects articles related to active research topics', 'research_topic', '{"topic_active": true}', 90, 365)
ON CONFLICT (rule_name) DO NOTHING;

-- Insert sample RAG research topics
INSERT INTO rag_research_topics (topic_name, topic_description, priority, research_frequency) VALUES
('Breaking News', 'High-priority breaking news events', 1, 'hourly'),
('Technology Trends', 'Emerging technology developments', 2, 'daily'),
('Political Developments', 'Major political events and policy changes', 2, 'daily'),
('Economic Indicators', 'Economic data and market trends', 3, 'daily'),
('Scientific Discoveries', 'New scientific research and discoveries', 3, 'weekly')
ON CONFLICT (topic_name) DO NOTHING;

-- ============================================================================
-- 10. GRANT PERMISSIONS
-- ============================================================================

-- Grant permissions to the database user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dockside_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dockside_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dockside_admin;

-- ============================================================================
-- 11. ADD COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE processed_articles IS 'Stores processed article content separate from raw RSS data';
COMMENT ON TABLE rag_context_requests IS 'Tracks RAG system requests for additional context';
COMMENT ON TABLE rag_research_topics IS 'Defines research topics for the RAG system';
COMMENT ON TABLE rag_research_sessions IS 'Tracks individual RAG research sessions';
COMMENT ON TABLE cleanup_protection_rules IS 'Defines rules for protecting articles from cleanup';

COMMENT ON COLUMN articles.processing_status IS 'Current processing status: raw, processing, ml_processed, processing_error';
COMMENT ON COLUMN articles.rag_keep_longer IS 'Flag to keep article longer for RAG research';
COMMENT ON COLUMN articles.rag_context_needed IS 'Flag indicating RAG context research is needed';
COMMENT ON COLUMN articles.rag_priority IS 'Priority level for RAG processing (0=normal, higher=more important)';

-- ============================================================================
-- 12. DISPLAY SCHEMA UPDATE SUMMARY
-- ============================================================================

-- Show all new tables
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename IN (
    'processed_articles',
    'rag_context_requests', 
    'rag_research_topics',
    'rag_research_sessions',
    'article_clusters',
    'ml_datasets',
    'ml_dataset_content',
    'intelligence_pipeline_results',
    'cleanup_protection_rules'
)
ORDER BY tablename;

-- Show all new functions
SELECT 
    proname as function_name,
    prosrc as function_source
FROM pg_proc 
WHERE proname IN (
    'get_ml_processing_stats',
    'get_articles_needing_rag_context',
    'get_cleanup_protection_status',
    'mark_article_for_rag'
)
ORDER BY proname;

-- Show schema update completion
SELECT 'Schema update completed successfully!' as status;
