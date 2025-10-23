-- Enhanced Timeline System for Chronological Event Extraction
-- This migration creates a comprehensive system for extracting and organizing
-- chronological events from article content, not just publication dates

-- ============================================================================
-- CHRONOLOGICAL EVENTS TABLE
-- ============================================================================

-- Enhanced timeline_events table with chronological extraction support
CREATE TABLE IF NOT EXISTS chronological_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    storyline_id VARCHAR(255) NOT NULL,
    
    -- Event identification
    title TEXT NOT NULL,
    description TEXT,
    event_type VARCHAR(100) DEFAULT 'general',
    
    -- Chronological information
    actual_event_date DATE,  -- The actual date when the event occurred
    actual_event_time TIME,
    relative_temporal_expression TEXT,  -- "yesterday", "last week", "three months ago"
    temporal_confidence NUMERIC(3,2) DEFAULT 0.0,  -- Confidence in date extraction
    
    -- Context and relationships
    historical_context TEXT,  -- "This follows the 2018 shutdown where..."
    related_events JSONB DEFAULT '[]'::jsonb,  -- References to other events
    event_sequence_position INTEGER,  -- Position in the overall story sequence
    
    -- Source information
    source_article_id INTEGER NOT NULL,
    source_text TEXT,  -- The specific text that mentioned this event
    source_paragraph INTEGER,  -- Which paragraph contained the reference
    source_sentence_start INTEGER,  -- Character position of sentence start
    source_sentence_end INTEGER,  -- Character position of sentence end
    
    -- Extraction metadata
    extraction_method VARCHAR(50) DEFAULT 'ml',  -- 'ml', 'rule_based', 'manual'
    extraction_confidence NUMERIC(3,2) DEFAULT 0.0,
    extraction_model VARCHAR(100),
    extraction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Event properties
    importance_score NUMERIC(3,2) DEFAULT 0.0,
    impact_level VARCHAR(50) DEFAULT 'medium',  -- 'low', 'medium', 'high', 'critical'
    location VARCHAR(255),
    entities JSONB DEFAULT '[]'::jsonb,
    tags TEXT[] DEFAULT '{}',
    
    -- Verification and quality
    verified BOOLEAN DEFAULT FALSE,
    verification_source VARCHAR(255),
    verification_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (source_article_id) REFERENCES articles(id) ON DELETE CASCADE
);

-- ============================================================================
-- TEMPORAL EXPRESSIONS TABLE
-- ============================================================================

-- Store extracted temporal expressions for analysis and normalization
CREATE TABLE IF NOT EXISTS temporal_expressions (
    id SERIAL PRIMARY KEY,
    expression_id VARCHAR(255) UNIQUE NOT NULL,
    chronological_event_id INTEGER NOT NULL,
    
    -- Expression details
    raw_expression TEXT NOT NULL,  -- "yesterday", "last week", "three months ago"
    normalized_date DATE,  -- The calculated actual date
    expression_type VARCHAR(50) NOT NULL,  -- 'relative', 'absolute', 'duration', 'period'
    temporal_anchor DATE,  -- The reference date for relative expressions
    
    -- Parsing results
    parsed_components JSONB DEFAULT '{}'::jsonb,  -- {"amount": 1, "unit": "week", "direction": "past"}
    parsing_confidence NUMERIC(3,2) DEFAULT 0.0,
    parsing_method VARCHAR(50) DEFAULT 'ml',  -- 'ml', 'regex', 'rule_based'
    
    -- Context
    context_sentence TEXT,  -- The full sentence containing the expression
    context_paragraph TEXT,  -- The full paragraph for additional context
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (chronological_event_id) REFERENCES chronological_events(id) ON DELETE CASCADE
);

-- ============================================================================
-- HISTORICAL CONTEXT TABLE
-- ============================================================================

-- Store historical context and references for better timeline understanding
CREATE TABLE IF NOT EXISTS historical_context (
    id SERIAL PRIMARY KEY,
    context_id VARCHAR(255) UNIQUE NOT NULL,
    storyline_id VARCHAR(255) NOT NULL,
    
    -- Context information
    context_type VARCHAR(100) NOT NULL,  -- 'previous_event', 'historical_reference', 'background'
    reference_text TEXT NOT NULL,  -- The text that references historical context
    referenced_period VARCHAR(100),  -- "2018 shutdown", "previous administration"
    referenced_date DATE,  -- If we can determine a specific date
    
    -- Source information
    source_article_id INTEGER NOT NULL,
    source_text TEXT,
    source_paragraph INTEGER,
    
    -- Context details
    context_description TEXT,
    relevance_score NUMERIC(3,2) DEFAULT 0.0,
    confidence_score NUMERIC(3,2) DEFAULT 0.0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (source_article_id) REFERENCES articles(id) ON DELETE CASCADE
);

-- ============================================================================
-- EVENT RELATIONSHIPS TABLE
-- ============================================================================

-- Store relationships between chronological events
CREATE TABLE IF NOT EXISTS event_relationships (
    id SERIAL PRIMARY KEY,
    relationship_id VARCHAR(255) UNIQUE NOT NULL,
    source_event_id INTEGER NOT NULL,
    target_event_id INTEGER NOT NULL,
    
    -- Relationship details
    relationship_type VARCHAR(100) NOT NULL,  -- 'causes', 'follows', 'parallel', 'conflicts'
    relationship_strength NUMERIC(3,2) DEFAULT 0.0,
    relationship_description TEXT,
    
    -- Temporal relationship
    temporal_relationship VARCHAR(100),  -- 'before', 'after', 'simultaneous', 'overlaps'
    time_gap_days INTEGER,  -- Days between events
    
    -- Confidence and verification
    confidence_score NUMERIC(3,2) DEFAULT 0.0,
    verified BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (source_event_id) REFERENCES chronological_events(id) ON DELETE CASCADE,
    FOREIGN KEY (target_event_id) REFERENCES chronological_events(id) ON DELETE CASCADE,
    UNIQUE(source_event_id, target_event_id, relationship_type)
);

-- ============================================================================
-- TIMELINE RECONSTRUCTION TABLE
-- ============================================================================

-- Store reconstructed timeline narratives
CREATE TABLE IF NOT EXISTS timeline_reconstructions (
    id SERIAL PRIMARY KEY,
    reconstruction_id VARCHAR(255) UNIQUE NOT NULL,
    storyline_id VARCHAR(255) NOT NULL,
    
    -- Reconstruction details
    reconstruction_type VARCHAR(100) NOT NULL,  -- 'chronological', 'thematic', 'causal'
    narrative_text TEXT NOT NULL,  -- The reconstructed narrative
    event_sequence JSONB DEFAULT '[]'::jsonb,  -- Ordered list of event IDs
    
    -- Quality metrics
    coherence_score NUMERIC(3,2) DEFAULT 0.0,
    completeness_score NUMERIC(3,2) DEFAULT 0.0,
    accuracy_score NUMERIC(3,2) DEFAULT 0.0,
    
    -- Generation metadata
    generation_method VARCHAR(50) DEFAULT 'ml',  -- 'ml', 'rule_based', 'hybrid'
    generation_model VARCHAR(100),
    generation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Chronological events indexes
CREATE INDEX IF NOT EXISTS idx_chronological_events_storyline_id ON chronological_events(storyline_id);
CREATE INDEX IF NOT EXISTS idx_chronological_events_actual_date ON chronological_events(actual_event_date);
CREATE INDEX IF NOT EXISTS idx_chronological_events_type ON chronological_events(event_type);
CREATE INDEX IF NOT EXISTS idx_chronological_events_importance ON chronological_events(importance_score);
CREATE INDEX IF NOT EXISTS idx_chronological_events_sequence ON chronological_events(event_sequence_position);
CREATE INDEX IF NOT EXISTS idx_chronological_events_source_article ON chronological_events(source_article_id);
CREATE INDEX IF NOT EXISTS idx_chronological_events_extraction_method ON chronological_events(extraction_method);

-- Temporal expressions indexes
CREATE INDEX IF NOT EXISTS idx_temporal_expressions_event_id ON temporal_expressions(chronological_event_id);
CREATE INDEX IF NOT EXISTS idx_temporal_expressions_normalized_date ON temporal_expressions(normalized_date);
CREATE INDEX IF NOT EXISTS idx_temporal_expressions_type ON temporal_expressions(expression_type);
CREATE INDEX IF NOT EXISTS idx_temporal_expressions_confidence ON temporal_expressions(parsing_confidence);

-- Historical context indexes
CREATE INDEX IF NOT EXISTS idx_historical_context_storyline_id ON historical_context(storyline_id);
CREATE INDEX IF NOT EXISTS idx_historical_context_type ON historical_context(context_type);
CREATE INDEX IF NOT EXISTS idx_historical_context_referenced_date ON historical_context(referenced_date);
CREATE INDEX IF NOT EXISTS idx_historical_context_relevance ON historical_context(relevance_score);

-- Event relationships indexes
CREATE INDEX IF NOT EXISTS idx_event_relationships_source ON event_relationships(source_event_id);
CREATE INDEX IF NOT EXISTS idx_event_relationships_target ON event_relationships(target_event_id);
CREATE INDEX IF NOT EXISTS idx_event_relationships_type ON event_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_event_relationships_temporal ON event_relationships(temporal_relationship);

-- Timeline reconstructions indexes
CREATE INDEX IF NOT EXISTS idx_timeline_reconstructions_storyline_id ON timeline_reconstructions(storyline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_reconstructions_type ON timeline_reconstructions(reconstruction_type);
CREATE INDEX IF NOT EXISTS idx_timeline_reconstructions_coherence ON timeline_reconstructions(coherence_score);

-- ============================================================================
-- FUNCTIONS FOR TEMPORAL PROCESSING
-- ============================================================================

-- Function to normalize temporal expressions
CREATE OR REPLACE FUNCTION normalize_temporal_expression(
    expression TEXT,
    anchor_date DATE DEFAULT CURRENT_DATE
) RETURNS DATE AS $$
DECLARE
    normalized_date DATE;
BEGIN
    -- This is a simplified version - in practice, this would use ML/NLP
    -- to parse expressions like "yesterday", "last week", "three months ago"
    
    expression := LOWER(TRIM(expression));
    
    -- Handle common relative expressions
    IF expression = 'yesterday' THEN
        normalized_date := anchor_date - INTERVAL '1 day';
    ELSIF expression = 'last week' THEN
        normalized_date := anchor_date - INTERVAL '1 week';
    ELSIF expression = 'last month' THEN
        normalized_date := anchor_date - INTERVAL '1 month';
    ELSIF expression = 'last year' THEN
        normalized_date := anchor_date - INTERVAL '1 year';
    ELSIF expression LIKE '% days ago' THEN
        normalized_date := anchor_date - INTERVAL (REGEXP_REPLACE(expression, '[^0-9]', '', 'g') || ' days');
    ELSIF expression LIKE '% weeks ago' THEN
        normalized_date := anchor_date - INTERVAL (REGEXP_REPLACE(expression, '[^0-9]', '', 'g') || ' weeks');
    ELSIF expression LIKE '% months ago' THEN
        normalized_date := anchor_date - INTERVAL (REGEXP_REPLACE(expression, '[^0-9]', '', 'g') || ' months');
    ELSIF expression LIKE '% years ago' THEN
        normalized_date := anchor_date - INTERVAL (REGEXP_REPLACE(expression, '[^0-9]', '', 'g') || ' years');
    ELSE
        -- Try to parse as absolute date
        BEGIN
            normalized_date := expression::DATE;
        EXCEPTION
            WHEN OTHERS THEN
                normalized_date := NULL;
        END;
    END IF;
    
    RETURN normalized_date;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate event sequence positions
CREATE OR REPLACE FUNCTION calculate_event_sequence(
    p_storyline_id VARCHAR(255)
) RETURNS VOID AS $$
BEGIN
    -- Update event_sequence_position based on actual_event_date
    UPDATE chronological_events 
    SET event_sequence_position = subquery.sequence_pos
    FROM (
        SELECT id, ROW_NUMBER() OVER (ORDER BY actual_event_date, actual_event_time) as sequence_pos
        FROM chronological_events 
        WHERE storyline_id = p_storyline_id
        AND actual_event_date IS NOT NULL
    ) subquery
    WHERE chronological_events.id = subquery.id;
END;
$$ LANGUAGE plpgsql;

-- Function to find related events
CREATE OR REPLACE FUNCTION find_related_events(
    p_event_id INTEGER,
    p_relationship_types TEXT[] DEFAULT ARRAY['causes', 'follows', 'parallel']
) RETURNS TABLE(
    related_event_id INTEGER,
    relationship_type VARCHAR(100),
    relationship_strength NUMERIC(3,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        CASE 
            WHEN er.source_event_id = p_event_id THEN er.target_event_id
            ELSE er.source_event_id
        END as related_event_id,
        er.relationship_type,
        er.relationship_strength
    FROM event_relationships er
    WHERE (er.source_event_id = p_event_id OR er.target_event_id = p_event_id)
    AND er.relationship_type = ANY(p_relationship_types)
    ORDER BY er.relationship_strength DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Trigger to update event sequence when events are added/modified
CREATE OR REPLACE FUNCTION trigger_update_event_sequence()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM calculate_event_sequence(NEW.storyline_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_event_sequence
    AFTER INSERT OR UPDATE OF actual_event_date, actual_event_time ON chronological_events
    FOR EACH ROW EXECUTE FUNCTION trigger_update_event_sequence();

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION trigger_update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_chronological_events_updated_at
    BEFORE UPDATE ON chronological_events
    FOR EACH ROW EXECUTE FUNCTION trigger_update_updated_at();

CREATE TRIGGER trigger_update_timeline_reconstructions_updated_at
    BEFORE UPDATE ON timeline_reconstructions
    FOR EACH ROW EXECUTE FUNCTION trigger_update_updated_at();

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View for chronological timeline
CREATE OR REPLACE VIEW chronological_timeline AS
SELECT 
    ce.id,
    ce.event_id,
    ce.storyline_id,
    ce.title,
    ce.description,
    ce.actual_event_date,
    ce.actual_event_time,
    ce.event_type,
    ce.importance_score,
    ce.impact_level,
    ce.location,
    ce.entities,
    ce.tags,
    ce.event_sequence_position,
    ce.temporal_confidence,
    ce.verified,
    a.title as source_article_title,
    a.source as source_publication,
    a.published_at as article_published_at
FROM chronological_events ce
JOIN articles a ON ce.source_article_id = a.id
ORDER BY ce.actual_event_date, ce.actual_event_time, ce.event_sequence_position;

-- View for temporal expressions analysis
CREATE OR REPLACE VIEW temporal_analysis AS
SELECT 
    te.id,
    te.expression_id,
    te.raw_expression,
    te.normalized_date,
    te.expression_type,
    te.parsing_confidence,
    te.parsing_method,
    ce.title as event_title,
    ce.actual_event_date,
    ce.storyline_id
FROM temporal_expressions te
JOIN chronological_events ce ON te.chronological_event_id = ce.id
ORDER BY te.normalized_date, te.parsing_confidence DESC;

-- View for event relationships
CREATE OR REPLACE VIEW event_relationship_network AS
SELECT 
    er.id,
    er.relationship_id,
    er.relationship_type,
    er.relationship_strength,
    er.temporal_relationship,
    er.time_gap_days,
    ce1.title as source_event_title,
    ce1.actual_event_date as source_event_date,
    ce2.title as target_event_title,
    ce2.actual_event_date as target_event_date
FROM event_relationships er
JOIN chronological_events ce1 ON er.source_event_id = ce1.id
JOIN chronological_events ce2 ON er.target_event_id = ce2.id
ORDER BY er.relationship_strength DESC;

-- ============================================================================
-- CONSTRAINTS AND VALIDATIONS
-- ============================================================================

-- Add check constraints
ALTER TABLE chronological_events ADD CONSTRAINT chk_importance_score CHECK (importance_score >= 0.0 AND importance_score <= 1.0);
ALTER TABLE chronological_events ADD CONSTRAINT chk_temporal_confidence CHECK (temporal_confidence >= 0.0 AND temporal_confidence <= 1.0);
ALTER TABLE chronological_events ADD CONSTRAINT chk_extraction_confidence CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0);

ALTER TABLE temporal_expressions ADD CONSTRAINT chk_parsing_confidence CHECK (parsing_confidence >= 0.0 AND parsing_confidence <= 1.0);

ALTER TABLE historical_context ADD CONSTRAINT chk_relevance_score CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0);
ALTER TABLE historical_context ADD CONSTRAINT chk_confidence_score CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);

ALTER TABLE event_relationships ADD CONSTRAINT chk_relationship_strength CHECK (relationship_strength >= 0.0 AND relationship_strength <= 1.0);
ALTER TABLE event_relationships ADD CONSTRAINT chk_confidence_score_rel CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);

ALTER TABLE timeline_reconstructions ADD CONSTRAINT chk_coherence_score CHECK (coherence_score >= 0.0 AND coherence_score <= 1.0);
ALTER TABLE timeline_reconstructions ADD CONSTRAINT chk_completeness_score CHECK (completeness_score >= 0.0 AND completeness_score <= 1.0);
ALTER TABLE timeline_reconstructions ADD CONSTRAINT chk_accuracy_score CHECK (accuracy_score >= 0.0 AND accuracy_score <= 1.0);

-- ============================================================================
-- MIGRATION COMPLETION
-- ============================================================================

-- Log migration completion
INSERT INTO deduplication_log (operation, status, details, created_at)
VALUES (
    'enhanced_timeline_system_migration',
    'completed',
    'Enhanced timeline system with chronological event extraction capabilities',
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

COMMIT;
