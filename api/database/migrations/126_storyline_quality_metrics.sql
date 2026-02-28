-- Migration 126: Storyline Quality Metrics and Context
-- Adds quality assessment columns and context management
-- Created: December 10, 2025
-- Version: 4.0.0

-- ============================================================================
-- ADD QUALITY METRICS TO STORYLINES TABLE (ALL DOMAINS)
-- ============================================================================

DO $$
DECLARE
    domain_schema_name TEXT;
    domain_record RECORD;
BEGIN
    -- Loop through all active domains
    FOR domain_record IN 
        SELECT d.schema_name 
        FROM public.domains d
        WHERE d.is_active = TRUE
    LOOP
        domain_schema_name := domain_record.schema_name;
        
        -- Add quality metrics columns if they don't exist
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS factual_accuracy_score DECIMAL(3,2) DEFAULT 0.0 
                CHECK (factual_accuracy_score >= 0.0 AND factual_accuracy_score <= 1.0);
        ', domain_schema_name);
        
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS narrative_quality_score DECIMAL(3,2) DEFAULT 0.0 
                CHECK (narrative_quality_score >= 0.0 AND narrative_quality_score <= 1.0);
        ', domain_schema_name);
        
        -- Add context management columns
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS historical_context TEXT;
        ', domain_schema_name);
        
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS background_information TEXT;
        ', domain_schema_name);
        
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS related_storyline_ids INTEGER[];
        ', domain_schema_name);
        
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS context_last_updated TIMESTAMP WITH TIME ZONE;
        ', domain_schema_name);
        
        -- Add evolution tracking
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS last_evolution_at TIMESTAMP WITH TIME ZONE;
        ', domain_schema_name);
        
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS evolution_count INTEGER DEFAULT 0;
        ', domain_schema_name);
        
        -- Add insights storage
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS insights JSONB DEFAULT ''[]''::jsonb;
        ', domain_schema_name);
        
        -- Add correlations storage
        EXECUTE format('
            ALTER TABLE %I.storylines 
            ADD COLUMN IF NOT EXISTS correlations JSONB DEFAULT ''[]''::jsonb;
        ', domain_schema_name);
        
        -- Add indexes for quality metrics (only if columns exist)
        -- Check if quality_score exists before creating index
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = domain_schema_name 
              AND table_name = 'storylines' 
              AND column_name = 'quality_score'
        ) THEN
            EXECUTE format('
                CREATE INDEX IF NOT EXISTS idx_%I_storylines_quality 
                ON %I.storylines(quality_score DESC);
            ', domain_schema_name, domain_schema_name);
        END IF;
        
        -- Check if coherence_score exists before creating index
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = domain_schema_name 
              AND table_name = 'storylines' 
              AND column_name = 'coherence_score'
        ) THEN
            EXECUTE format('
                CREATE INDEX IF NOT EXISTS idx_%I_storylines_coherence 
                ON %I.storylines(coherence_score DESC);
            ', domain_schema_name, domain_schema_name);
        END IF;
        
        -- Evolution index (created after last_evolution_at column is added)
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%I_storylines_evolution 
            ON %I.storylines(last_evolution_at DESC) 
            WHERE last_evolution_at IS NOT NULL;
        ', domain_schema_name, domain_schema_name);
        
        RAISE NOTICE 'Added quality metrics to %.storylines', domain_schema_name;
    END LOOP;
END $$;

-- ============================================================================
-- CREATE STORYLINE INSIGHTS TABLE (PUBLIC SCHEMA - SHARED)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.storyline_insights (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL,
    domain_schema VARCHAR(50) NOT NULL,  -- 'politics', 'finance', 'science_tech'
    insight_type VARCHAR(50) NOT NULL CHECK (insight_type IN (
        'pattern', 'trend', 'prediction', 'correlation', 'anomaly', 'summary'
    )),
    title VARCHAR(300) NOT NULL,
    description TEXT NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.0 
        CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    supporting_evidence TEXT[],
    implications TEXT[],
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT unique_storyline_insight UNIQUE (storyline_id, domain_schema, insight_type, title)
);

CREATE INDEX IF NOT EXISTS idx_storyline_insights_storyline 
ON public.storyline_insights(storyline_id, domain_schema);

CREATE INDEX IF NOT EXISTS idx_storyline_insights_type 
ON public.storyline_insights(insight_type, confidence_score DESC);

-- ============================================================================
-- CREATE STORYLINE CORRELATIONS TABLE (PUBLIC SCHEMA - SHARED)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.storyline_correlations (
    id SERIAL PRIMARY KEY,
    storyline_id_1 INTEGER NOT NULL,
    storyline_id_2 INTEGER NOT NULL,
    domain_schema VARCHAR(50) NOT NULL,
    correlation_type VARCHAR(50) NOT NULL CHECK (correlation_type IN (
        'temporal', 'entity', 'thematic', 'causal', 'geographic', 'source'
    )),
    correlation_strength DECIMAL(3,2) DEFAULT 0.0 
        CHECK (correlation_strength >= 0.0 AND correlation_strength <= 1.0),
    shared_entities TEXT[],
    shared_keywords TEXT[],
    temporal_overlap_days INTEGER,
    evidence TEXT,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT unique_correlation UNIQUE (storyline_id_1, storyline_id_2, domain_schema, correlation_type),
    CONSTRAINT different_storylines CHECK (storyline_id_1 != storyline_id_2)
);

CREATE INDEX IF NOT EXISTS idx_storyline_correlations_storyline1 
ON public.storyline_correlations(storyline_id_1, domain_schema);

CREATE INDEX IF NOT EXISTS idx_storyline_correlations_storyline2 
ON public.storyline_correlations(storyline_id_2, domain_schema);

CREATE INDEX IF NOT EXISTS idx_storyline_correlations_strength 
ON public.storyline_correlations(correlation_strength DESC);

-- ============================================================================
-- CREATE EMERGING STORYLINES TABLE (PUBLIC SCHEMA - SHARED)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.emerging_storylines (
    id SERIAL PRIMARY KEY,
    domain_schema VARCHAR(50) NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    confidence_score DECIMAL(3,2) DEFAULT 0.0 
        CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    article_count INTEGER DEFAULT 0,
    trend_score DECIMAL(5,2) DEFAULT 0.0,
    key_entities TEXT[],
    key_keywords TEXT[],
    source_diversity INTEGER DEFAULT 0,
    first_detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'emerging' CHECK (status IN (
        'emerging', 'confirmed', 'dismissed', 'merged'
    )),
    merged_into_storyline_id INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_emerging_storylines_domain 
ON public.emerging_storylines(domain_schema, status);

CREATE INDEX IF NOT EXISTS idx_emerging_storylines_confidence 
ON public.emerging_storylines(confidence_score DESC, trend_score DESC);

CREATE INDEX IF NOT EXISTS idx_emerging_storylines_detected 
ON public.emerging_storylines(first_detected_at DESC);

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON COLUMN public.storyline_insights.insight_type IS 'Type of insight: pattern, trend, prediction, correlation, anomaly, summary';
COMMENT ON COLUMN public.storyline_correlations.correlation_type IS 'Type of correlation: temporal, entity, thematic, causal, geographic, source';
COMMENT ON COLUMN public.emerging_storylines.status IS 'Status: emerging (newly detected), confirmed (promoted to storyline), dismissed (false positive), merged (merged into existing storyline)';

