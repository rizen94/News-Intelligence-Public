-- Migration 010: Expert Analysis Tables
-- Creates database schema for expert analysis integration
-- Created: 2025-01-09

-- Expert Sources Table
CREATE TABLE IF NOT EXISTS expert_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id VARCHAR(100) NOT NULL UNIQUE,
    source_name VARCHAR(200) NOT NULL,
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('academic_research', 'think_tank_reports', 'expert_opinions', 'policy_papers', 'industry_analysis', 'international_organizations')),
    credibility_level VARCHAR(20) NOT NULL CHECK (credibility_level IN ('high', 'medium', 'low', 'unknown')),
    expertise_areas JSONB DEFAULT '[]'::jsonb,
    institutional_affiliation VARCHAR(200),
    publication_date DATE,
    source_url TEXT,
    source_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for expert_sources
CREATE INDEX IF NOT EXISTS idx_expert_sources_source_id ON expert_sources(source_id);
CREATE INDEX IF NOT EXISTS idx_expert_sources_type ON expert_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_expert_sources_credibility ON expert_sources(credibility_level);
CREATE INDEX IF NOT EXISTS idx_expert_sources_created_at ON expert_sources(created_at);

-- Expert Analyses Table
CREATE TABLE IF NOT EXISTS expert_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    analysis_id VARCHAR(100) NOT NULL UNIQUE,
    source_id VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    analysis_content TEXT NOT NULL,
    key_insights JSONB DEFAULT '[]'::jsonb,
    methodology TEXT,
    confidence_score DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    relevance_score DECIMAL(3,2) DEFAULT 0.0 CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0),
    credibility_score DECIMAL(3,2) DEFAULT 0.0 CHECK (credibility_score >= 0.0 AND credibility_score <= 1.0),
    supporting_evidence JSONB DEFAULT '[]'::jsonb,
    limitations JSONB DEFAULT '[]'::jsonb,
    analysis_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for expert_analyses
CREATE INDEX IF NOT EXISTS idx_expert_analyses_storyline_id ON expert_analyses(storyline_id);
CREATE INDEX IF NOT EXISTS idx_expert_analyses_analysis_id ON expert_analyses(analysis_id);
CREATE INDEX IF NOT EXISTS idx_expert_analyses_source_id ON expert_analyses(source_id);
CREATE INDEX IF NOT EXISTS idx_expert_analyses_source_type ON expert_analyses(source_type);
CREATE INDEX IF NOT EXISTS idx_expert_analyses_confidence ON expert_analyses(confidence_score);
CREATE INDEX IF NOT EXISTS idx_expert_analyses_credibility ON expert_analyses(credibility_score);
CREATE INDEX IF NOT EXISTS idx_expert_analyses_created_at ON expert_analyses(created_at);

-- Expert Synthesis Table
CREATE TABLE IF NOT EXISTS expert_synthesis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    synthesis_id VARCHAR(100) NOT NULL UNIQUE,
    consensus_analysis TEXT NOT NULL,
    key_disagreements JSONB DEFAULT '[]'::jsonb,
    expert_consensus_score DECIMAL(3,2) DEFAULT 0.0 CHECK (expert_consensus_score >= 0.0 AND expert_consensus_score <= 1.0),
    synthesis_quality_score DECIMAL(3,2) DEFAULT 0.0 CHECK (synthesis_quality_score >= 0.0 AND synthesis_quality_score <= 1.0),
    methodology_notes TEXT,
    synthesis_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for expert_synthesis
CREATE INDEX IF NOT EXISTS idx_expert_synthesis_storyline_id ON expert_synthesis(storyline_id);
CREATE INDEX IF NOT EXISTS idx_expert_synthesis_synthesis_id ON expert_synthesis(synthesis_id);
CREATE INDEX IF NOT EXISTS idx_expert_synthesis_consensus ON expert_synthesis(expert_consensus_score);
CREATE INDEX IF NOT EXISTS idx_expert_synthesis_quality ON expert_synthesis(synthesis_quality_score);
CREATE INDEX IF NOT EXISTS idx_expert_synthesis_created_at ON expert_synthesis(created_at);

-- Add foreign key constraints
DO $$
BEGIN
    -- Add foreign key for expert_analyses to storylines
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_expert_analyses_storyline_id'
    ) THEN
        ALTER TABLE expert_analyses 
        ADD CONSTRAINT fk_expert_analyses_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
    END IF;
    
    -- Add foreign key for expert_synthesis to storylines
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_expert_synthesis_storyline_id'
    ) THEN
        ALTER TABLE expert_synthesis 
        ADD CONSTRAINT fk_expert_synthesis_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
    END IF;
    
    -- Add foreign key for expert_analyses to expert_sources
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_expert_analyses_source_id'
    ) THEN
        ALTER TABLE expert_analyses 
        ADD CONSTRAINT fk_expert_analyses_source_id 
        FOREIGN KEY (source_id) REFERENCES expert_sources(source_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create update triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_expert_sources_updated_at 
    BEFORE UPDATE ON expert_sources 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_expert_analyses_updated_at 
    BEFORE UPDATE ON expert_analyses 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_expert_synthesis_updated_at 
    BEFORE UPDATE ON expert_synthesis 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default expert source types
INSERT INTO expert_sources (source_id, source_name, source_type, credibility_level, expertise_areas, institutional_affiliation) VALUES
('academic_research_default', 'Academic Research Database', 'academic_research', 'high', '["political_science", "economics", "sociology", "international_relations", "public_policy"]', 'Academic Research Institution'),
('think_tank_default', 'Think Tank Research Network', 'think_tank_reports', 'high', '["policy_analysis", "strategic_studies", "economic_policy", "foreign_policy", "social_policy"]', 'Think Tank Research Institution'),
('expert_opinions_default', 'Expert Opinion Network', 'expert_opinions', 'medium', '["professional_expertise", "industry_knowledge", "practical_experience", "field_expertise"]', 'Professional Expert Network'),
('policy_papers_default', 'Policy Papers Database', 'policy_papers', 'high', '["government_policy", "regulatory_analysis", "public_administration", "governance", "institutional_policy"]', 'Government Policy Institution'),
('industry_analysis_default', 'Industry Analysis Network', 'industry_analysis', 'medium', '["market_analysis", "industry_trends", "business_intelligence", "sector_analysis", "economic_analysis"]', 'Industry Analysis Institution'),
('international_orgs_default', 'International Organizations Network', 'international_organizations', 'high', '["international_relations", "multilateral_cooperation", "global_governance", "international_law", "development"]', 'International Organization')
ON CONFLICT (source_id) DO NOTHING;

-- Add table comments
COMMENT ON TABLE expert_sources IS 'Expert analysis sources and their metadata';
COMMENT ON TABLE expert_analyses IS 'Individual expert analyses for storylines';
COMMENT ON TABLE expert_synthesis IS 'Synthesized expert analysis results';
COMMENT ON COLUMN expert_sources.source_type IS 'Type of expert source: academic_research, think_tank_reports, expert_opinions, policy_papers, industry_analysis, international_organizations';
COMMENT ON COLUMN expert_sources.credibility_level IS 'Credibility level: high, medium, low, unknown';
COMMENT ON COLUMN expert_analyses.confidence_score IS 'Confidence score for the analysis (0.0 to 1.0)';
COMMENT ON COLUMN expert_analyses.relevance_score IS 'Relevance score for the storyline (0.0 to 1.0)';
COMMENT ON COLUMN expert_analyses.credibility_score IS 'Credibility score for the source (0.0 to 1.0)';
COMMENT ON COLUMN expert_synthesis.expert_consensus_score IS 'Consensus score among experts (0.0 to 1.0)';
COMMENT ON COLUMN expert_synthesis.synthesis_quality_score IS 'Quality score for the synthesis (0.0 to 1.0)';

