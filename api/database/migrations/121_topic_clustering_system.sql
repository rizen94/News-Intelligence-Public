-- Migration 121: Topic Clustering and Auto-Tagging System with Iterative Learning
-- Comprehensive topic clustering system with feedback loop for continuous improvement
-- Created: November 2025
-- Version: 4.1.0

-- ============================================================================
-- TOPIC CLUSTERING SYSTEM: Topics, Assignments, and Learning
-- ============================================================================

-- Topics Table: Stores discovered and curated topics
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    topic_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Topic Information
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),  -- politics, business, technology, health, etc.
    keywords TEXT[],  -- Array of related keywords
    
    -- Iterative Learning Metrics
    confidence_score DECIMAL(3,2) DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    accuracy_score DECIMAL(3,2) DEFAULT 0.5 CHECK (accuracy_score >= 0.0 AND accuracy_score <= 1.0),
    review_count INTEGER DEFAULT 0,  -- Number of times reviewed/validated
    correct_assignments INTEGER DEFAULT 0,  -- Number of correct assignments
    incorrect_assignments INTEGER DEFAULT 0,  -- Number of incorrect assignments
    
    -- Learning Data
    learning_data JSONB DEFAULT '{}',  -- Stores patterns, examples, feedback
    last_improved_at TIMESTAMP WITH TIME ZONE,  -- When accuracy improved
    improvement_trend DECIMAL(3,2) DEFAULT 0.0,  -- Trend in accuracy over time
    
    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'reviewed', 'archived', 'merged')),
    is_auto_generated BOOLEAN DEFAULT TRUE,  -- True if ML-generated, False if manually created
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    -- Constraints
    CONSTRAINT unique_topic_name UNIQUE (name)
);

-- Article-Topic Assignments: Links articles to topics with confidence scores
CREATE TABLE IF NOT EXISTS article_topic_assignments (
    id SERIAL PRIMARY KEY,
    assignment_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Relationships
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    
    -- Assignment Metrics
    confidence_score DECIMAL(3,2) DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    relevance_score DECIMAL(3,2) DEFAULT 0.5 CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0),
    
    -- Iterative Learning Feedback
    is_validated BOOLEAN DEFAULT FALSE,  -- Has been reviewed by human
    is_correct BOOLEAN,  -- NULL = not reviewed, TRUE = correct, FALSE = incorrect
    feedback_notes TEXT,  -- Human feedback on the assignment
    feedback_source VARCHAR(50),  -- 'user', 'admin', 'system'
    
    -- Learning Context
    assignment_method VARCHAR(50) DEFAULT 'auto' CHECK (assignment_method IN ('auto', 'manual', 'learned', 'hybrid')),
    model_version VARCHAR(50),  -- Which model/version made this assignment
    assignment_context JSONB DEFAULT '{}',  -- Context used for assignment (keywords, entities, etc.)
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP WITH TIME ZONE,
    validated_by VARCHAR(100),
    
    -- Constraints
    CONSTRAINT unique_article_topic UNIQUE (article_id, topic_id)
);

-- Topic Clusters: Groups of related topics
CREATE TABLE IF NOT EXISTS topic_clusters (
    id SERIAL PRIMARY KEY,
    cluster_uuid UUID DEFAULT uuid_generate_v4(),
    
    -- Cluster Information
    cluster_name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    
    -- Cluster Metrics
    topic_count INTEGER DEFAULT 0,
    article_count INTEGER DEFAULT 0,
    average_confidence DECIMAL(3,2) DEFAULT 0.0,
    
    -- Learning Data
    cluster_patterns JSONB DEFAULT '{}',  -- Patterns that define this cluster
    learning_data JSONB DEFAULT '{}',
    
    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'reviewed', 'archived')),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Topic Cluster Memberships: Links topics to clusters
CREATE TABLE IF NOT EXISTS topic_cluster_memberships (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    cluster_id INTEGER NOT NULL REFERENCES topic_clusters(id) ON DELETE CASCADE,
    membership_confidence DECIMAL(3,2) DEFAULT 0.5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_topic_cluster UNIQUE (topic_id, cluster_id)
);

-- Topic Learning History: Tracks improvements over time
CREATE TABLE IF NOT EXISTS topic_learning_history (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    
    -- Learning Event
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('review', 'correction', 'validation', 'improvement')),
    event_data JSONB DEFAULT '{}',
    
    -- Metrics Snapshot
    accuracy_before DECIMAL(3,2),
    accuracy_after DECIMAL(3,2),
    confidence_before DECIMAL(3,2),
    confidence_after DECIMAL(3,2),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Topics indexes
CREATE INDEX IF NOT EXISTS idx_topics_name ON topics(name);
CREATE INDEX IF NOT EXISTS idx_topics_category ON topics(category);
CREATE INDEX IF NOT EXISTS idx_topics_status ON topics(status);
CREATE INDEX IF NOT EXISTS idx_topics_confidence ON topics(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_topics_accuracy ON topics(accuracy_score DESC);
CREATE INDEX IF NOT EXISTS idx_topics_keywords ON topics USING GIN(keywords);

-- Article-Topic Assignment indexes
CREATE INDEX IF NOT EXISTS idx_article_topic_article ON article_topic_assignments(article_id);
CREATE INDEX IF NOT EXISTS idx_article_topic_topic ON article_topic_assignments(topic_id);
CREATE INDEX IF NOT EXISTS idx_article_topic_confidence ON article_topic_assignments(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_article_topic_validated ON article_topic_assignments(is_validated);
CREATE INDEX IF NOT EXISTS idx_article_topic_correct ON article_topic_assignments(is_correct) WHERE is_correct IS NOT NULL;

-- Topic Clusters indexes
CREATE INDEX IF NOT EXISTS idx_topic_clusters_category ON topic_clusters(category);
CREATE INDEX IF NOT EXISTS idx_topic_clusters_status ON topic_clusters(status);

-- Topic Learning History indexes
CREATE INDEX IF NOT EXISTS idx_topic_learning_topic ON topic_learning_history(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_learning_event_type ON topic_learning_history(event_type);
CREATE INDEX IF NOT EXISTS idx_topic_learning_created ON topic_learning_history(created_at DESC);

-- ============================================================================
-- FUNCTIONS FOR ITERATIVE LEARNING
-- ============================================================================

-- Function: Update topic accuracy after feedback
CREATE OR REPLACE FUNCTION update_topic_accuracy()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_validated = TRUE AND NEW.is_correct IS NOT NULL THEN
        -- Update topic accuracy metrics
        UPDATE topics
        SET
            review_count = review_count + 1,
            correct_assignments = CASE 
                WHEN NEW.is_correct = TRUE THEN correct_assignments + 1 
                ELSE correct_assignments 
            END,
            incorrect_assignments = CASE 
                WHEN NEW.is_correct = FALSE THEN incorrect_assignments + 1 
                ELSE incorrect_assignments 
            END,
            accuracy_score = CASE 
                WHEN (correct_assignments + incorrect_assignments + 1) > 0 
                THEN (correct_assignments::DECIMAL + CASE WHEN NEW.is_correct THEN 1 ELSE 0 END) / 
                     (correct_assignments + incorrect_assignments + 1)
                ELSE 0.5
            END,
            last_improved_at = CASE 
                WHEN (CASE WHEN NEW.is_correct THEN 1 ELSE 0 END) > 0 
                THEN CURRENT_TIMESTAMP 
                ELSE last_improved_at 
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.topic_id;
        
        -- Record learning history
        INSERT INTO topic_learning_history (
            topic_id, 
            event_type, 
            event_data,
            accuracy_before,
            accuracy_after,
            created_by
        )
        SELECT 
            NEW.topic_id,
            'validation',
            jsonb_build_object(
                'article_id', NEW.article_id,
                'is_correct', NEW.is_correct,
                'feedback_notes', NEW.feedback_notes
            ),
            (SELECT accuracy_score FROM topics WHERE id = NEW.topic_id),
            (SELECT accuracy_score FROM topics WHERE id = NEW.topic_id),
            NEW.validated_by
        FROM topics WHERE id = NEW.topic_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Update topic accuracy on assignment validation
CREATE TRIGGER trigger_update_topic_accuracy
    AFTER UPDATE OF is_validated, is_correct ON article_topic_assignments
    FOR EACH ROW
    WHEN (NEW.is_validated = TRUE AND (OLD.is_validated IS DISTINCT FROM NEW.is_validated OR OLD.is_correct IS DISTINCT FROM NEW.is_correct))
    EXECUTE FUNCTION update_topic_accuracy();

-- Function: Calculate topic confidence based on assignments
CREATE OR REPLACE FUNCTION calculate_topic_confidence(topic_id_param INTEGER)
RETURNS DECIMAL(3,2) AS $$
DECLARE
    avg_confidence DECIMAL(3,2);
BEGIN
    SELECT AVG(confidence_score) INTO avg_confidence
    FROM article_topic_assignments
    WHERE topic_id = topic_id_param
    AND is_validated = TRUE
    AND is_correct = TRUE;
    
    RETURN COALESCE(avg_confidence, 0.5);
END;
$$ LANGUAGE plpgsql;

-- Function: Get topics needing review (low accuracy or high incorrect count)
CREATE OR REPLACE FUNCTION get_topics_needing_review(threshold DECIMAL DEFAULT 0.6)
RETURNS TABLE (
    topic_id INTEGER,
    topic_name VARCHAR(200),
    accuracy_score DECIMAL(3,2),
    review_count INTEGER,
    incorrect_assignments INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id,
        t.name,
        t.accuracy_score,
        t.review_count,
        t.incorrect_assignments
    FROM topics t
    WHERE t.accuracy_score < threshold
    AND t.review_count > 0
    ORDER BY t.incorrect_assignments DESC, t.accuracy_score ASC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA: Common Topic Categories
-- ============================================================================

-- Insert common topic categories as seed data
INSERT INTO topics (name, description, category, is_auto_generated, confidence_score, accuracy_score)
VALUES
    ('Politics', 'Political news and analysis', 'politics', FALSE, 0.9, 0.9),
    ('Business', 'Business and economic news', 'business', FALSE, 0.9, 0.9),
    ('Technology', 'Technology and innovation news', 'technology', FALSE, 0.9, 0.9),
    ('Health', 'Health and medical news', 'health', FALSE, 0.9, 0.9),
    ('Environment', 'Environmental and climate news', 'environment', FALSE, 0.9, 0.9),
    ('International', 'International news and relations', 'international', FALSE, 0.9, 0.9)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE topics IS 'Stores discovered and curated topics with iterative learning metrics';
COMMENT ON TABLE article_topic_assignments IS 'Links articles to topics with confidence scores and feedback';
COMMENT ON TABLE topic_clusters IS 'Groups of related topics for better organization';
COMMENT ON TABLE topic_learning_history IS 'Tracks learning improvements over time for topics';
COMMENT ON FUNCTION update_topic_accuracy() IS 'Automatically updates topic accuracy when assignments are validated';
COMMENT ON FUNCTION calculate_topic_confidence(topic_id_param INTEGER) IS 'Calculates topic confidence based on validated assignments';
COMMENT ON FUNCTION get_topics_needing_review(threshold DECIMAL) IS 'Returns topics that need review based on accuracy threshold';


