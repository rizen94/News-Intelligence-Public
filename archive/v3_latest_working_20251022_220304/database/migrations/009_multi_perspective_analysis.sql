-- Migration 009: Multi-Perspective Analysis System
-- Creates database schema for enhanced analytical depth features
-- Created: 2025-01-09

-- Analysis Perspectives Table
CREATE TABLE IF NOT EXISTS analysis_perspectives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    perspective_type VARCHAR(50) NOT NULL,
    analysis_content TEXT NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    key_points JSONB DEFAULT '[]'::jsonb,
    supporting_evidence JSONB DEFAULT '[]'::jsonb,
    source_articles JSONB DEFAULT '[]'::jsonb,
    analysis_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for analysis_perspectives
CREATE INDEX IF NOT EXISTS idx_analysis_perspectives_storyline_id ON analysis_perspectives(storyline_id);
CREATE INDEX IF NOT EXISTS idx_analysis_perspectives_type ON analysis_perspectives(perspective_type);
CREATE INDEX IF NOT EXISTS idx_analysis_perspectives_confidence ON analysis_perspectives(confidence_score);
CREATE INDEX IF NOT EXISTS idx_analysis_perspectives_created_at ON analysis_perspectives(created_at);

-- Multi-Perspective Analysis Results Table
CREATE TABLE IF NOT EXISTS multi_perspective_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    analysis_version INTEGER DEFAULT 1,
    synthesized_analysis TEXT NOT NULL,
    perspective_agreement JSONB DEFAULT '{}'::jsonb,
    key_disagreements JSONB DEFAULT '[]'::jsonb,
    consensus_score DECIMAL(3,2) DEFAULT 0.0 CHECK (consensus_score >= 0.0 AND consensus_score <= 1.0),
    analysis_quality_score DECIMAL(3,2) DEFAULT 0.0 CHECK (analysis_quality_score >= 0.0 AND analysis_quality_score <= 1.0),
    processing_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for multi_perspective_analysis
CREATE INDEX IF NOT EXISTS idx_multi_perspective_analysis_storyline_id ON multi_perspective_analysis(storyline_id);
CREATE INDEX IF NOT EXISTS idx_multi_perspective_analysis_version ON multi_perspective_analysis(analysis_version);
CREATE INDEX IF NOT EXISTS idx_multi_perspective_analysis_consensus ON multi_perspective_analysis(consensus_score);

-- Impact Assessments Table (for Phase 3)
CREATE TABLE IF NOT EXISTS impact_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    impact_dimension VARCHAR(50) NOT NULL,
    impact_score DECIMAL(3,2) DEFAULT 0.0 CHECK (impact_score >= 0.0 AND impact_score <= 1.0),
    impact_description TEXT NOT NULL,
    subcategory_impacts JSONB DEFAULT '{}'::jsonb,
    supporting_evidence JSONB DEFAULT '[]'::jsonb,
    confidence_level DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence_level >= 0.0 AND confidence_level <= 1.0),
    risk_level VARCHAR(20) DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    mitigation_strategies JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for impact_assessments
CREATE INDEX IF NOT EXISTS idx_impact_assessments_storyline_id ON impact_assessments(storyline_id);
CREATE INDEX IF NOT EXISTS idx_impact_assessments_dimension ON impact_assessments(impact_dimension);
CREATE INDEX IF NOT EXISTS idx_impact_assessments_risk_level ON impact_assessments(risk_level);

-- Historical Patterns Table (for Phase 4)
CREATE TABLE IF NOT EXISTS historical_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    pattern_description TEXT NOT NULL,
    historical_events JSONB DEFAULT '[]'::jsonb,
    similarity_score DECIMAL(3,2) DEFAULT 0.0 CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
    precedent_analysis TEXT,
    lessons_learned JSONB DEFAULT '[]'::jsonb,
    pattern_confidence DECIMAL(3,2) DEFAULT 0.0 CHECK (pattern_confidence >= 0.0 AND pattern_confidence <= 1.0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for historical_patterns
CREATE INDEX IF NOT EXISTS idx_historical_patterns_storyline_id ON historical_patterns(storyline_id);
CREATE INDEX IF NOT EXISTS idx_historical_patterns_type ON historical_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_historical_patterns_similarity ON historical_patterns(similarity_score);

-- Predictive Analysis Table (for Phase 5)
CREATE TABLE IF NOT EXISTS predictive_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    prediction_horizon VARCHAR(20) NOT NULL CHECK (prediction_horizon IN ('short_term', 'medium_term', 'long_term')),
    prediction_content TEXT NOT NULL,
    confidence_level DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence_level >= 0.0 AND confidence_level <= 1.0),
    key_scenarios JSONB DEFAULT '[]'::jsonb,
    uncertainty_factors JSONB DEFAULT '[]'::jsonb,
    monitoring_indicators JSONB DEFAULT '[]'::jsonb,
    prediction_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for predictive_analysis
CREATE INDEX IF NOT EXISTS idx_predictive_analysis_storyline_id ON predictive_analysis(storyline_id);
CREATE INDEX IF NOT EXISTS idx_predictive_analysis_horizon ON predictive_analysis(prediction_horizon);
CREATE INDEX IF NOT EXISTS idx_predictive_analysis_confidence ON predictive_analysis(confidence_level);

-- Analysis Quality Metrics Table
CREATE TABLE IF NOT EXISTS analysis_quality_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    completeness_score DECIMAL(3,2) DEFAULT 0.0 CHECK (completeness_score >= 0.0 AND completeness_score <= 1.0),
    accuracy_score DECIMAL(3,2) DEFAULT 0.0 CHECK (accuracy_score >= 0.0 AND accuracy_score <= 1.0),
    readability_score DECIMAL(3,2) DEFAULT 0.0 CHECK (readability_score >= 0.0 AND readability_score <= 1.0),
    timeliness_score DECIMAL(3,2) DEFAULT 0.0 CHECK (timeliness_score >= 0.0 AND timeliness_score <= 1.0),
    user_engagement_score DECIMAL(3,2) DEFAULT 0.0 CHECK (user_engagement_score >= 0.0 AND user_engagement_score <= 1.0),
    overall_quality_score DECIMAL(3,2) DEFAULT 0.0 CHECK (overall_quality_score >= 0.0 AND overall_quality_score <= 1.0),
    quality_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for analysis_quality_metrics
CREATE INDEX IF NOT EXISTS idx_analysis_quality_storyline_id ON analysis_quality_metrics(storyline_id);
CREATE INDEX IF NOT EXISTS idx_analysis_quality_type ON analysis_quality_metrics(analysis_type);
CREATE INDEX IF NOT EXISTS idx_analysis_quality_overall ON analysis_quality_metrics(overall_quality_score);

-- Add foreign key constraints
-- Note: These will only be added if the referenced tables exist

-- Add foreign key to storylines table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'storylines') THEN
        ALTER TABLE analysis_perspectives 
        ADD CONSTRAINT fk_analysis_perspectives_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
        
        ALTER TABLE multi_perspective_analysis 
        ADD CONSTRAINT fk_multi_perspective_analysis_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
        
        ALTER TABLE impact_assessments 
        ADD CONSTRAINT fk_impact_assessments_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
        
        ALTER TABLE historical_patterns 
        ADD CONSTRAINT fk_historical_patterns_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
        
        ALTER TABLE predictive_analysis 
        ADD CONSTRAINT fk_predictive_analysis_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
        
        ALTER TABLE analysis_quality_metrics 
        ADD CONSTRAINT fk_analysis_quality_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers to all tables
CREATE TRIGGER update_analysis_perspectives_updated_at BEFORE UPDATE ON analysis_perspectives FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_multi_perspective_analysis_updated_at BEFORE UPDATE ON multi_perspective_analysis FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_impact_assessments_updated_at BEFORE UPDATE ON impact_assessments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_historical_patterns_updated_at BEFORE UPDATE ON historical_patterns FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_predictive_analysis_updated_at BEFORE UPDATE ON predictive_analysis FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_analysis_quality_metrics_updated_at BEFORE UPDATE ON analysis_quality_metrics FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default perspective types
INSERT INTO analysis_perspectives (storyline_id, perspective_type, analysis_content, confidence_score) VALUES
('00000000-0000-0000-0000-000000000000', 'government_official', 'Default government perspective template', 0.0),
('00000000-0000-0000-0000-000000000000', 'opposition_critical', 'Default opposition perspective template', 0.0),
('00000000-0000-0000-0000-000000000000', 'expert_academic', 'Default expert perspective template', 0.0),
('00000000-0000-0000-0000-000000000000', 'international', 'Default international perspective template', 0.0),
('00000000-0000-0000-0000-000000000000', 'economic', 'Default economic perspective template', 0.0),
('00000000-0000-0000-0000-000000000000', 'social_civil', 'Default social perspective template', 0.0)
ON CONFLICT DO NOTHING;

-- Insert default impact dimensions
INSERT INTO impact_assessments (storyline_id, impact_dimension, impact_score, impact_description, risk_level) VALUES
('00000000-0000-0000-0000-000000000000', 'political', 0.0, 'Default political impact template', 'low'),
('00000000-0000-0000-0000-000000000000', 'economic', 0.0, 'Default economic impact template', 'low'),
('00000000-0000-0000-0000-000000000000', 'social', 0.0, 'Default social impact template', 'low'),
('00000000-0000-0000-0000-000000000000', 'environmental', 0.0, 'Default environmental impact template', 'low'),
('00000000-0000-0000-0000-000000000000', 'technological', 0.0, 'Default technological impact template', 'low'),
('00000000-0000-0000-0000-000000000000', 'international', 0.0, 'Default international impact template', 'low')
ON CONFLICT DO NOTHING;

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO newsapp;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO newsapp;

COMMENT ON TABLE analysis_perspectives IS 'Individual perspective analyses for storylines';
COMMENT ON TABLE multi_perspective_analysis IS 'Synthesized multi-perspective analysis results';
COMMENT ON TABLE impact_assessments IS 'Impact assessments across different dimensions';
COMMENT ON TABLE historical_patterns IS 'Historical pattern recognition and precedent analysis';
COMMENT ON TABLE predictive_analysis IS 'Predictive analysis and future outlook';
COMMENT ON TABLE analysis_quality_metrics IS 'Quality metrics for analysis components';

