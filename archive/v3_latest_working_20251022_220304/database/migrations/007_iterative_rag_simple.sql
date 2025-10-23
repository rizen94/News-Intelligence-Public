-- Migration 007: Iterative RAG System Tables (Simplified)
-- Creates core tables for the iterative RAG dossier system

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
    final_synthesis JSONB DEFAULT '{}'
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

-- Create basic indexes
CREATE INDEX IF NOT EXISTS idx_rag_dossiers_article_id ON rag_dossiers(article_id);
CREATE INDEX IF NOT EXISTS idx_rag_dossiers_dossier_id ON rag_dossiers(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_dossiers_status ON rag_dossiers(is_complete, plateau_reached);

CREATE INDEX IF NOT EXISTS idx_rag_iterations_dossier_id ON rag_iterations(dossier_id);
CREATE INDEX IF NOT EXISTS idx_rag_iterations_phase ON rag_iterations(phase);
CREATE INDEX IF NOT EXISTS idx_rag_iterations_timestamp ON rag_iterations(timestamp);

-- Add comments
COMMENT ON TABLE rag_dossiers IS 'Stores iterative RAG dossiers that build comprehensive analysis over multiple iterations';
COMMENT ON TABLE rag_iterations IS 'Stores individual iterations within each RAG dossier';
