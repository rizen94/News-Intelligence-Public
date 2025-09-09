-- Migration 007: Iterative RAG System Tables
-- Creates tables for the iterative RAG dossier system

-- Table for storing RAG dossiers
CREATE TABLE IF NOT EXISTS rag_dossiers (
    id SERIAL PRIMARY KEY,
    dossier_id VARCHAR(16) UNIQUE NOT NULL,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    total_iterations INTEGER DEFAULT 0,
    current_phase VARCHAR(20) DEFAULT 'timeline',
    is_complete BOOLEAN DEFAULT FALSE,
    plateau_reached BOOLEAN DEFAULT FALSE,
    total_articles_analyzed INTEGER DEFAULT 0,
    total_entities_found INTEGER DEFAULT 0,
    historical_depth_years INTEGER DEFAULT 0,
    final_timeline JSONB DEFAULT '{}',
    final_context JSONB DEFAULT '{}',
    final_analysis JSONB DEFAULT '{}',
    final_synthesis JSONB DEFAULT '{}',
    -- Indexes will be created separately
);

-- Table for storing individual RAG iterations
CREATE TABLE IF NOT EXISTS rag_iterations (
    id SERIAL PRIMARY KEY,
    dossier_id VARCHAR(16) NOT NULL REFERENCES rag_dossiers(dossier_id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    phase VARCHAR(20) NOT NULL,
    input_tags JSONB DEFAULT '[]',
    output_tags JSONB DEFAULT '[]',
    new_articles_found INTEGER DEFAULT 0,
    new_entities_found INTEGER DEFAULT 0,
    new_insights JSONB DEFAULT '[]',
    processing_time FLOAT DEFAULT 0.0,
    plateau_score FLOAT DEFAULT 0.0,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    UNIQUE(dossier_id, iteration_number)
);

-- Table for storing RAG context requests (enhanced from existing)
CREATE TABLE IF NOT EXISTS rag_context_requests (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    dossier_id VARCHAR(16) REFERENCES rag_dossiers(dossier_id) ON DELETE SET NULL,
    iteration_number INTEGER,
    request_type VARCHAR(20) DEFAULT 'simple', -- 'simple', 'gdelt', 'iterative'
    keywords JSONB DEFAULT '[]',
    context_data JSONB DEFAULT '{}',
    processing_time FLOAT DEFAULT 0.0,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Indexes will be created separately
);

-- Table for storing RAG research topics (enhanced from existing)
CREATE TABLE IF NOT EXISTS rag_research_topics (
    id SERIAL PRIMARY KEY,
    dossier_id VARCHAR(16) REFERENCES rag_dossiers(dossier_id) ON DELETE CASCADE,
    topic_name VARCHAR(255) NOT NULL,
    topic_description TEXT,
    keywords JSONB DEFAULT '[]',
    research_depth INTEGER DEFAULT 1, -- 1-5 scale
    historical_scope_years INTEGER DEFAULT 5,
    articles_analyzed INTEGER DEFAULT 0,
    entities_found INTEGER DEFAULT 0,
    insights JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_researched TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Indexes will be created separately
);

-- Table for storing RAG plateau detection metrics
CREATE TABLE IF NOT EXISTS rag_plateau_metrics (
    id SERIAL PRIMARY KEY,
    dossier_id VARCHAR(16) NOT NULL REFERENCES rag_dossiers(dossier_id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    phase VARCHAR(20) NOT NULL,
    new_information_score FLOAT DEFAULT 0.0,
    information_density FLOAT DEFAULT 0.0,
    entity_novelty_score FLOAT DEFAULT 0.0,
    temporal_coverage_score FLOAT DEFAULT 0.0,
    overall_plateau_score FLOAT DEFAULT 0.0,
    plateau_threshold FLOAT DEFAULT 0.1,
    is_plateau BOOLEAN DEFAULT FALSE,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Indexes will be created separately
);

-- Table for storing RAG tag evolution
CREATE TABLE IF NOT EXISTS rag_tag_evolution (
    id SERIAL PRIMARY KEY,
    dossier_id VARCHAR(16) NOT NULL REFERENCES rag_dossiers(dossier_id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    phase VARCHAR(20) NOT NULL,
    input_tags JSONB DEFAULT '[]',
    output_tags JSONB DEFAULT '[]',
    tag_sources JSONB DEFAULT '{}', -- Track where each tag came from
    tag_confidence_scores JSONB DEFAULT '{}', -- Confidence scores for each tag
    tag_frequency_counts JSONB DEFAULT '{}', -- How often tags appear
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Indexes will be created separately
);

-- Table for storing RAG performance metrics
CREATE TABLE IF NOT EXISTS rag_performance_metrics (
    id SERIAL PRIMARY KEY,
    dossier_id VARCHAR(16) REFERENCES rag_dossiers(dossier_id) ON DELETE CASCADE,
    iteration_number INTEGER,
    phase VARCHAR(20),
    processing_time FLOAT DEFAULT 0.0,
    memory_usage_mb FLOAT DEFAULT 0.0,
    api_calls_made INTEGER DEFAULT 0,
    articles_processed INTEGER DEFAULT 0,
    entities_extracted INTEGER DEFAULT 0,
    insights_generated INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 1.0,
    measured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Indexes will be created separately
);

-- Create views for easier querying
CREATE OR REPLACE VIEW rag_dossier_summary AS
SELECT 
    d.dossier_id,
    d.article_id,
    a.title as article_title,
    d.created_at,
    d.last_updated,
    d.total_iterations,
    d.current_phase,
    d.is_complete,
    d.plateau_reached,
    d.total_articles_analyzed,
    d.total_entities_found,
    d.historical_depth_years,
    COUNT(i.id) as actual_iterations,
    AVG(i.processing_time) as avg_processing_time,
    AVG(i.plateau_score) as avg_plateau_score,
    SUM(i.new_articles_found) as total_new_articles,
    SUM(i.new_entities_found) as total_new_entities
FROM rag_dossiers d
LEFT JOIN articles a ON d.article_id = a.id
LEFT JOIN rag_iterations i ON d.dossier_id = i.dossier_id
GROUP BY d.dossier_id, d.article_id, a.title, d.created_at, d.last_updated,
         d.total_iterations, d.current_phase, d.is_complete, d.plateau_reached,
         d.total_articles_analyzed, d.total_entities_found, d.historical_depth_years;

CREATE OR REPLACE VIEW rag_iteration_progress AS
SELECT 
    d.dossier_id,
    d.article_id,
    a.title as article_title,
    i.iteration_number,
    i.phase,
    i.timestamp,
    i.processing_time,
    i.plateau_score,
    i.new_articles_found,
    i.new_entities_found,
    i.success,
    i.error_message,
    LAG(i.plateau_score) OVER (PARTITION BY d.dossier_id ORDER BY i.iteration_number) as prev_plateau_score,
    i.plateau_score - LAG(i.plateau_score) OVER (PARTITION BY d.dossier_id ORDER BY i.iteration_number) as plateau_score_change
FROM rag_dossiers d
LEFT JOIN articles a ON d.article_id = a.id
LEFT JOIN rag_iterations i ON d.dossier_id = i.dossier_id
ORDER BY d.dossier_id, i.iteration_number;

-- Insert sample configuration data
INSERT INTO rag_research_topics (topic_name, topic_description, keywords, research_depth, historical_scope_years) VALUES
('Global Politics', 'International political developments and conflicts', '["politics", "international", "conflict", "diplomacy"]', 3, 10),
('Technology Innovation', 'Breakthroughs in technology and digital transformation', '["technology", "innovation", "digital", "breakthrough"]', 4, 5),
('Economic Trends', 'Global economic indicators and market movements', '["economy", "markets", "finance", "trade"]', 3, 15),
('Environmental Issues', 'Climate change and environmental policy', '["environment", "climate", "sustainability", "policy"]', 4, 20),
('Social Movements', 'Social change and cultural developments', '["social", "culture", "movement", "change"]', 2, 8)
ON CONFLICT DO NOTHING;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_rag_dossiers_article_id ON rag_dossiers(article_id);
CREATE INDEX IF NOT EXISTS idx_rag_dossiers_dossier_id ON rag_dossiers(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_dossiers_status ON rag_dossiers(is_complete, plateau_reached);
CREATE INDEX IF NOT EXISTS idx_rag_dossiers_updated ON rag_dossiers(last_updated);

CREATE INDEX IF NOT EXISTS idx_rag_iterations_dossier_id ON rag_iterations(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_iterations_phase ON rag_iterations(phase);
CREATE INDEX IF NOT EXISTS idx_rag_iterations_timestamp ON rag_iterations(timestamp);
CREATE INDEX IF NOT EXISTS idx_rag_iterations_success ON rag_iterations(success);

CREATE INDEX IF NOT EXISTS idx_rag_context_article_id ON rag_context_requests(article_id);
CREATE INDEX IF NOT EXISTS idx_rag_context_dossier_id ON rag_context_requests(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_context_type ON rag_context_requests(request_type);
CREATE INDEX IF NOT EXISTS idx_rag_context_created ON rag_context_requests(created_at);

CREATE INDEX IF NOT EXISTS idx_rag_topics_dossier_id ON rag_research_topics(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_topics_name ON rag_research_topics(topic_name);
CREATE INDEX IF NOT EXISTS idx_rag_topics_depth ON rag_research_topics(research_depth);
CREATE INDEX IF NOT EXISTS idx_rag_topics_scope ON rag_research_topics(historical_scope_years);

CREATE INDEX IF NOT EXISTS idx_rag_plateau_dossier_id ON rag_plateau_metrics(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_plateau_iteration ON rag_plateau_metrics(iteration_number);
CREATE INDEX IF NOT EXISTS idx_rag_plateau_phase ON rag_plateau_metrics(phase);
CREATE INDEX IF NOT EXISTS idx_rag_plateau_score ON rag_plateau_metrics(overall_plateau_score);
CREATE INDEX IF NOT EXISTS idx_rag_plateau_detected ON rag_plateau_metrics(is_plateau);

CREATE INDEX IF NOT EXISTS idx_rag_tags_dossier_id ON rag_tag_evolution(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_tags_iteration ON rag_tag_evolution(iteration_number);
CREATE INDEX IF NOT EXISTS idx_rag_tags_phase ON rag_tag_evolution(phase);
CREATE INDEX IF NOT EXISTS idx_rag_tags_created ON rag_tag_evolution(created_at);

CREATE INDEX IF NOT EXISTS idx_rag_perf_dossier_id ON rag_performance_metrics(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_perf_phase ON rag_performance_metrics(phase);
CREATE INDEX IF NOT EXISTS idx_rag_perf_time ON rag_performance_metrics(processing_time);
CREATE INDEX IF NOT EXISTS idx_rag_perf_success ON rag_performance_metrics(success_rate);
CREATE INDEX IF NOT EXISTS idx_rag_perf_measured ON rag_performance_metrics(measured_at);

-- Composite indexes for better performance
CREATE INDEX IF NOT EXISTS idx_rag_dossiers_composite ON rag_dossiers(article_id, is_complete, plateau_reached);
CREATE INDEX IF NOT EXISTS idx_rag_iterations_composite ON rag_iterations(dossier_id, iteration_number, phase);
CREATE INDEX IF NOT EXISTS idx_rag_context_composite ON rag_context_requests(article_id, request_type, created_at);

-- Add comments for documentation
COMMENT ON TABLE rag_dossiers IS 'Stores iterative RAG dossiers that build comprehensive analysis over multiple iterations';
COMMENT ON TABLE rag_iterations IS 'Stores individual iterations within each RAG dossier';
COMMENT ON TABLE rag_context_requests IS 'Enhanced table for storing RAG context requests with dossier linkage';
COMMENT ON TABLE rag_research_topics IS 'Stores research topics and their configuration for iterative RAG';
COMMENT ON TABLE rag_plateau_metrics IS 'Stores metrics for detecting when RAG iterations reach a plateau';
COMMENT ON TABLE rag_tag_evolution IS 'Tracks how search tags evolve through RAG iterations';
COMMENT ON TABLE rag_performance_metrics IS 'Stores performance metrics for RAG processing';

COMMENT ON COLUMN rag_dossiers.dossier_id IS 'Unique 16-character identifier for the dossier';
COMMENT ON COLUMN rag_dossiers.current_phase IS 'Current phase: timeline, context, analysis, or synthesis';
COMMENT ON COLUMN rag_dossiers.plateau_reached IS 'Whether the dossier has reached a plateau of new information';
COMMENT ON COLUMN rag_dossiers.historical_depth_years IS 'How far back in time the analysis extends';

COMMENT ON COLUMN rag_iterations.phase IS 'Phase of this iteration: timeline, context, analysis, or synthesis';
COMMENT ON COLUMN rag_iterations.plateau_score IS 'Score indicating how much new information was found (0-1)';
COMMENT ON COLUMN rag_iterations.input_tags IS 'Tags used as input for this iteration';
COMMENT ON COLUMN rag_iterations.output_tags IS 'Tags generated as output for next iteration';

COMMENT ON COLUMN rag_plateau_metrics.new_information_score IS 'Score for amount of new information found';
COMMENT ON COLUMN rag_plateau_metrics.information_density IS 'Density of information per article';
COMMENT ON COLUMN rag_plateau_metrics.entity_novelty_score IS 'Novelty score for extracted entities';
COMMENT ON COLUMN rag_plateau_metrics.temporal_coverage_score IS 'Score for temporal coverage of events';
