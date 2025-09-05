-- Timeline Features Database Migration
-- Adds support for ML-powered timeline generation

-- Create timeline_events table for storing ML-generated timeline events
CREATE TABLE IF NOT EXISTS timeline_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    storyline_id VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    event_time TIME,
    source VARCHAR(255),
    url TEXT,
    importance_score NUMERIC(3,2) DEFAULT 0.0,
    event_type VARCHAR(100) DEFAULT 'general',
    location VARCHAR(255),
    entities JSONB DEFAULT '[]'::jsonb,
    tags TEXT[] DEFAULT '{}',
    ml_generated BOOLEAN DEFAULT true,
    confidence_score NUMERIC(3,2) DEFAULT 0.0,
    source_article_ids INTEGER[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for timeline_events
CREATE INDEX IF NOT EXISTS idx_timeline_events_storyline_id ON timeline_events(storyline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_date ON timeline_events(event_date);
CREATE INDEX IF NOT EXISTS idx_timeline_events_importance_score ON timeline_events(importance_score);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_type ON timeline_events(event_type);
CREATE INDEX IF NOT EXISTS idx_timeline_events_ml_generated ON timeline_events(ml_generated);

-- Add timeline-related columns to articles table
ALTER TABLE articles ADD COLUMN IF NOT EXISTS timeline_relevance_score NUMERIC(3,2) DEFAULT 0.0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS timeline_processed BOOLEAN DEFAULT false;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS timeline_events_generated INTEGER DEFAULT 0;

-- Create indexes for new article columns
CREATE INDEX IF NOT EXISTS idx_articles_timeline_relevance ON articles(timeline_relevance_score);
CREATE INDEX IF NOT EXISTS idx_articles_timeline_processed ON articles(timeline_processed);

-- Create timeline_periods table for grouping events
CREATE TABLE IF NOT EXISTS timeline_periods (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    period VARCHAR(50) NOT NULL, -- e.g., '2024-01', '2024-Q1'
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    event_count INTEGER DEFAULT 0,
    key_events JSONB DEFAULT '[]'::jsonb,
    summary TEXT,
    ml_generated BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(storyline_id, period)
);

-- Create indexes for timeline_periods
CREATE INDEX IF NOT EXISTS idx_timeline_periods_storyline_id ON timeline_periods(storyline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_periods_period ON timeline_periods(period);

-- Create timeline_milestones table for key events
CREATE TABLE IF NOT EXISTS timeline_milestones (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    milestone_type VARCHAR(100) NOT NULL, -- 'major', 'turning_point', 'crisis', 'resolution'
    significance_score NUMERIC(3,2) DEFAULT 0.0,
    impact_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES timeline_events(event_id) ON DELETE CASCADE
);

-- Create indexes for timeline_milestones
CREATE INDEX IF NOT EXISTS idx_timeline_milestones_storyline_id ON timeline_milestones(storyline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_milestones_milestone_type ON timeline_milestones(milestone_type);

-- Create timeline_analysis table for ML analysis results
CREATE TABLE IF NOT EXISTS timeline_analysis (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    analysis_date DATE NOT NULL,
    total_events INTEGER DEFAULT 0,
    high_importance_events INTEGER DEFAULT 0,
    event_types JSONB DEFAULT '{}'::jsonb,
    key_entities JSONB DEFAULT '[]'::jsonb,
    geographic_coverage JSONB DEFAULT '[]'::jsonb,
    sentiment_trend NUMERIC(3,2) DEFAULT 0.0,
    complexity_score NUMERIC(3,2) DEFAULT 0.0,
    narrative_coherence NUMERIC(3,2) DEFAULT 0.0,
    ml_insights JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(storyline_id, analysis_date)
);

-- Create indexes for timeline_analysis
CREATE INDEX IF NOT EXISTS idx_timeline_analysis_storyline_id ON timeline_analysis(storyline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_analysis_date ON timeline_analysis(analysis_date);

-- Add timeline-related columns to story_expectations table
ALTER TABLE story_expectations ADD COLUMN IF NOT EXISTS timeline_enabled BOOLEAN DEFAULT true;
ALTER TABLE story_expectations ADD COLUMN IF NOT EXISTS timeline_auto_generate BOOLEAN DEFAULT true;
ALTER TABLE story_expectations ADD COLUMN IF NOT EXISTS timeline_min_importance NUMERIC(3,2) DEFAULT 0.3;
ALTER TABLE story_expectations ADD COLUMN IF NOT EXISTS timeline_max_events_per_day INTEGER DEFAULT 10;
ALTER TABLE story_expectations ADD COLUMN IF NOT EXISTS timeline_last_generated TIMESTAMP;

-- Create timeline_generation_log table for tracking ML generation
CREATE TABLE IF NOT EXISTS timeline_generation_log (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    generation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    events_generated INTEGER DEFAULT 0,
    articles_analyzed INTEGER DEFAULT 0,
    ml_model_used VARCHAR(255),
    generation_time_seconds INTEGER DEFAULT 0,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    parameters JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for timeline_generation_log
CREATE INDEX IF NOT EXISTS idx_timeline_generation_log_storyline_id ON timeline_generation_log(storyline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_generation_log_date ON timeline_generation_log(generation_date);

-- Create timeline_event_sources table for tracking article sources
CREATE TABLE IF NOT EXISTS timeline_event_sources (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL,
    article_id INTEGER NOT NULL,
    relevance_score NUMERIC(3,2) DEFAULT 0.0,
    contribution_type VARCHAR(100) DEFAULT 'primary', -- 'primary', 'supporting', 'context'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES timeline_events(event_id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    UNIQUE(event_id, article_id)
);

-- Create indexes for timeline_event_sources
CREATE INDEX IF NOT EXISTS idx_timeline_event_sources_event_id ON timeline_event_sources(event_id);
CREATE INDEX IF NOT EXISTS idx_timeline_event_sources_article_id ON timeline_event_sources(article_id);

-- Add constraints and triggers
ALTER TABLE timeline_events ADD CONSTRAINT chk_importance_score CHECK (importance_score >= 0.0 AND importance_score <= 1.0);
ALTER TABLE timeline_events ADD CONSTRAINT chk_confidence_score CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_timeline_events_updated_at BEFORE UPDATE ON timeline_events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_timeline_periods_updated_at BEFORE UPDATE ON timeline_periods FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default timeline configuration
INSERT INTO system_config (key, value, description) VALUES 
('timeline_ml_enabled', 'true', 'Enable ML-powered timeline generation'),
('timeline_ollama_url', 'http://localhost:11434', 'Ollama API URL for timeline generation'),
('timeline_model_name', 'llama3.1:70b-instruct-q4_K_M', 'Default model for timeline generation'),
('timeline_max_events_per_storyline', '100', 'Maximum events to generate per storyline'),
('timeline_min_confidence_score', '0.3', 'Minimum confidence score for timeline events'),
('timeline_auto_generate_interval', '24', 'Hours between automatic timeline generation')
ON CONFLICT (key) DO NOTHING;

-- Update existing storylines to enable timeline features
UPDATE story_expectations 
SET timeline_enabled = true, 
    timeline_auto_generate = true,
    timeline_min_importance = 0.3,
    timeline_max_events_per_day = 10
WHERE timeline_enabled IS NULL;

COMMIT;
