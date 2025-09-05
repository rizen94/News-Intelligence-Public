-- News Intelligence System v2.1.1 - Event Tracking Enhancement
-- This script adds the missing components for proper event tracking, temporal context,
-- and accurate event summarization

-- ============================================================================
-- 1. ENHANCE ARTICLES TABLE WITH EVENT TRACKING METADATA
-- ============================================================================

-- Add event tracking columns to articles table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'event_id'
    ) THEN
        ALTER TABLE articles ADD COLUMN event_id INTEGER;
        RAISE NOTICE 'Added event_id column to articles table';
    ELSE
        RAISE NOTICE 'event_id column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'location_entities'
    ) THEN
        ALTER TABLE articles ADD COLUMN location_entities JSONB;
        RAISE NOTICE 'Added location_entities column to articles table';
    ELSE
        RAISE NOTICE 'location_entities column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'person_entities'
    ) THEN
        ALTER TABLE articles ADD COLUMN person_entities JSONB;
        RAISE NOTICE 'Added person_entities column to articles table';
    ELSE
        RAISE NOTICE 'person_entities column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'organization_entities'
    ) THEN
        ALTER TABLE articles ADD COLUMN organization_entities JSONB;
        RAISE NOTICE 'Added organization_entities column to articles table';
    ELSE
        RAISE NOTICE 'organization_entities column already exists in articles table';
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'event_confidence'
    ) THEN
        ALTER TABLE articles ADD COLUMN event_confidence DECIMAL(5,2) DEFAULT 0.0;
        RAISE NOTICE 'Added event_confidence column to articles table';
    ELSE
        RAISE NOTICE 'event_confidence column already exists in articles table';
    END IF;
END $$;

-- ============================================================================
-- 2. CREATE EVENTS TABLE FOR EVENT TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS events (
    event_id SERIAL PRIMARY KEY,
    
    -- Event identification
    event_name VARCHAR(500) NOT NULL,
    event_type VARCHAR(100) NOT NULL, -- 'breaking_news', 'ongoing_event', 'announcement', 'investigation'
    event_category VARCHAR(100), -- 'politics', 'technology', 'health', 'economy', 'environment', 'crime'
    
    -- Event metadata
    event_description TEXT,
    event_keywords TEXT[],
    event_entities JSONB, -- All entities associated with this event
    
    -- Temporal tracking
    event_start_date TIMESTAMP,
    event_end_date TIMESTAMP,
    event_duration_hours INTEGER,
    is_ongoing BOOLEAN DEFAULT TRUE,
    
    -- Geographic context
    primary_location VARCHAR(255),
    location_coordinates POINT, -- (latitude, longitude)
    affected_regions TEXT[],
    
    -- Event relationships
    parent_event_id INTEGER REFERENCES events(event_id),
    related_event_ids INTEGER[],
    
    -- Event evolution tracking
    event_stage VARCHAR(100) DEFAULT 'developing', -- 'developing', 'peak', 'resolution', 'follow_up'
    event_importance_score DECIMAL(5,2) DEFAULT 0.0,
    event_verification_status VARCHAR(50) DEFAULT 'unverified', -- 'unverified', 'verified', 'disputed'
    
    -- ML processing data
    event_summary TEXT,
    event_timeline JSONB,
    event_analysis JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 3. CREATE EVENT TIMELINE TABLE FOR TEMPORAL TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS event_timeline_entries (
    entry_id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(event_id) ON DELETE CASCADE,
    
    -- Timeline entry details
    entry_type VARCHAR(100) NOT NULL, -- 'milestone', 'update', 'reaction', 'development'
    entry_title VARCHAR(500) NOT NULL,
    entry_description TEXT,
    
    -- Temporal information
    entry_timestamp TIMESTAMP NOT NULL,
    entry_order INTEGER NOT NULL, -- For proper timeline sequencing
    
    -- Source information
    source_article_ids INTEGER[],
    source_confidence DECIMAL(5,2),
    
    -- Entry metadata
    entry_entities JSONB,
    entry_keywords TEXT[],
    entry_impact_score DECIMAL(5,2),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 4. CREATE ENTITY RELATIONSHIP TABLE FOR CONTEXT TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_relationships (
    relationship_id SERIAL PRIMARY KEY,
    
    -- Entity identification
    entity_type VARCHAR(50) NOT NULL, -- 'person', 'organization', 'location', 'concept'
    entity_name VARCHAR(255) NOT NULL,
    entity_id VARCHAR(100), -- External ID if available
    
    -- Relationship details
    related_entity_type VARCHAR(50) NOT NULL,
    related_entity_name VARCHAR(255) NOT NULL,
    related_entity_id VARCHAR(100),
    
    -- Relationship metadata
    relationship_type VARCHAR(100) NOT NULL, -- 'works_for', 'located_in', 'involved_in', 'mentions'
    relationship_strength DECIMAL(5,2) DEFAULT 1.0,
    relationship_confidence DECIMAL(5,2) DEFAULT 1.0,
    
    -- Context information
    context_articles INTEGER[],
    relationship_start_date DATE,
    relationship_end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 5. CREATE EVENT CLUSTERING TABLE FOR SIMILARITY ANALYSIS
-- ============================================================================

CREATE TABLE IF NOT EXISTS event_clusters (
    cluster_id SERIAL PRIMARY KEY,
    
    -- Cluster identification
    cluster_name VARCHAR(500),
    cluster_type VARCHAR(100) NOT NULL, -- 'topic', 'geographic', 'temporal', 'entity_based'
    
    -- Cluster composition
    event_ids INTEGER[] NOT NULL,
    article_ids INTEGER[] NOT NULL,
    
    -- Clustering metadata
    cluster_keywords TEXT[],
    cluster_entities JSONB,
    cluster_geographic_scope TEXT[],
    cluster_temporal_span JSONB, -- {start_date, end_date, duration}
    
    -- Similarity metrics
    cluster_cohesion_score DECIMAL(5,2),
    cluster_similarity_matrix JSONB,
    
    -- ML processing results
    cluster_summary TEXT,
    cluster_analysis JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 6. CREATE CONTEXT TRACKING TABLE FOR BACKGROUND INFORMATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS context_tracking (
    context_id SERIAL PRIMARY KEY,
    
    -- Context identification
    context_type VARCHAR(100) NOT NULL, -- 'background', 'historical', 'related_events', 'expert_analysis'
    context_topic VARCHAR(255) NOT NULL,
    
    -- Context content
    context_summary TEXT,
    context_details JSONB,
    context_sources TEXT[],
    
    -- Context relationships
    related_event_ids INTEGER[],
    related_article_ids INTEGER[],
    related_entity_ids TEXT[],
    
    -- Context metadata
    context_confidence DECIMAL(5,2),
    context_relevance_score DECIMAL(5,2),
    context_last_verified TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 7. CREATE EVENT VERIFICATION TABLE FOR FACT CHECKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS event_verification (
    verification_id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(event_id) ON DELETE CASCADE,
    
    -- Verification details
    verification_type VARCHAR(100) NOT NULL, -- 'fact_check', 'source_verification', 'expert_review'
    verification_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'in_progress', 'verified', 'disputed', 'false'
    
    -- Verification results
    verification_score DECIMAL(5,2),
    verification_notes TEXT,
    verification_sources TEXT[],
    
    -- Verification metadata
    verified_by VARCHAR(255),
    verification_date TIMESTAMP,
    verification_confidence DECIMAL(5,2),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 8. CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Events table indexes
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(event_category);
CREATE INDEX IF NOT EXISTS idx_events_start_date ON events(event_start_date);
CREATE INDEX IF NOT EXISTS idx_events_ongoing ON events(is_ongoing);
CREATE INDEX IF NOT EXISTS idx_events_importance ON events(event_importance_score);
CREATE INDEX IF NOT EXISTS idx_events_location ON events(primary_location);
CREATE INDEX IF NOT EXISTS idx_events_parent ON events(parent_event_id);

-- Event timeline indexes
CREATE INDEX IF NOT EXISTS idx_event_timeline_event_id ON event_timeline_entries(event_id);
CREATE INDEX IF NOT EXISTS idx_event_timeline_timestamp ON event_timeline_entries(entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_event_timeline_order ON event_timeline_entries(entry_order);
CREATE INDEX IF NOT EXISTS idx_event_timeline_type ON event_timeline_entries(entry_type);

-- Entity relationship indexes
CREATE INDEX IF NOT EXISTS idx_entity_relationships_entity_type ON entity_relationships(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_entity_name ON entity_relationships(entity_name);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_type ON entity_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_active ON entity_relationships(is_active);

-- Event cluster indexes
CREATE INDEX IF NOT EXISTS idx_event_clusters_type ON event_clusters(cluster_type);
CREATE INDEX IF NOT EXISTS idx_event_clusters_cohesion ON event_clusters(cluster_cohesion_score);

-- Context tracking indexes
CREATE INDEX IF NOT EXISTS idx_context_tracking_type ON context_tracking(context_type);
CREATE INDEX IF NOT EXISTS idx_context_tracking_topic ON context_tracking(context_topic);
CREATE INDEX IF NOT EXISTS idx_context_tracking_relevance ON context_tracking(context_relevance_score);

-- Event verification indexes
CREATE INDEX IF NOT EXISTS idx_event_verification_event_id ON event_verification(event_id);
CREATE INDEX IF NOT EXISTS idx_event_verification_status ON event_verification(verification_status);
CREATE INDEX IF NOT EXISTS idx_event_verification_score ON event_verification(verification_score);

-- ============================================================================
-- 9. CREATE FUNCTIONS FOR EVENT TRACKING
-- ============================================================================

-- Function to get event timeline
CREATE OR REPLACE FUNCTION get_event_timeline(event_id_param INTEGER)
RETURNS TABLE(
    entry_id INTEGER,
    entry_type VARCHAR(100),
    entry_title VARCHAR(500),
    entry_description TEXT,
    entry_timestamp TIMESTAMP,
    entry_order INTEGER,
    entry_impact_score DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ete.entry_id,
        ete.entry_type,
        ete.entry_title,
        ete.entry_description,
        ete.entry_timestamp,
        ete.entry_order,
        ete.entry_impact_score
    FROM event_timeline_entries ete
    WHERE ete.event_id = event_id_param
    ORDER BY ete.entry_order, ete.entry_timestamp;
END;
$$ LANGUAGE plpgsql;

-- Function to get related events
CREATE OR REPLACE FUNCTION get_related_events(event_id_param INTEGER, max_related INTEGER DEFAULT 10)
RETURNS TABLE(
    event_id INTEGER,
    event_name VARCHAR(500),
    event_type VARCHAR(100),
    relationship_strength DECIMAL(5,2),
    common_entities INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.event_id,
        e.event_name,
        e.event_type,
        CASE 
            WHEN e.parent_event_id = event_id_param THEN 1.0
            WHEN event_id_param = ANY(e.related_event_ids) THEN 0.8
            ELSE 0.5
        END as relationship_strength,
        CASE 
            WHEN e.event_entities IS NOT NULL THEN 
                (SELECT COUNT(*) FROM jsonb_object_keys(e.event_entities) AS entity_count)
            ELSE 0
        END as common_entities
    FROM events e
    WHERE e.event_id != event_id_param
      AND (e.parent_event_id = event_id_param 
           OR event_id_param = ANY(e.related_event_ids)
           OR e.event_entities ?| (SELECT event_entities->'entities' FROM events WHERE event_id = event_id_param))
    ORDER BY relationship_strength DESC, common_entities DESC
    LIMIT max_related;
END;
$$ LANGUAGE plpgsql;

-- Function to get event context
CREATE OR REPLACE FUNCTION get_event_context(event_id_param INTEGER)
RETURNS TABLE(
    context_type VARCHAR(100),
    context_topic VARCHAR(255),
    context_summary TEXT,
    context_relevance_score DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ct.context_type,
        ct.context_topic,
        ct.context_summary,
        ct.context_relevance_score
    FROM context_tracking ct
    WHERE event_id_param = ANY(ct.related_event_ids)
       OR ct.context_topic ILIKE '%' || (SELECT event_name FROM events WHERE event_id = event_id_param) || '%'
    ORDER BY ct.context_relevance_score DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to update event importance score
CREATE OR REPLACE FUNCTION update_event_importance(event_id_param INTEGER)
RETURNS DECIMAL(5,2) AS $$
DECLARE
    new_score DECIMAL(5,2);
BEGIN
    SELECT 
        CASE 
            WHEN e.event_type = 'breaking_news' THEN 0.3
            WHEN e.event_type = 'ongoing_event' THEN 0.2
            ELSE 0.1
        END +
        CASE 
            WHEN e.is_ongoing THEN 0.2
            ELSE 0.0
        END +
        CASE 
            WHEN e.event_verification_status = 'verified' THEN 0.2
            WHEN e.event_verification_status = 'disputed' THEN 0.1
            ELSE 0.0
        END +
        COALESCE(e.event_importance_score, 0.0) * 0.3
    INTO new_score
    FROM events e
    WHERE e.event_id = event_id_param;
    
    UPDATE events 
    SET event_importance_score = new_score,
        updated_at = NOW()
    WHERE event_id = event_id_param;
    
    RETURN new_score;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. CREATE TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Trigger for updating event last_updated_at
CREATE OR REPLACE FUNCTION update_event_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_event_last_updated
    BEFORE UPDATE ON events
    FOR EACH ROW
    EXECUTE FUNCTION update_event_last_updated();

-- Trigger for updating event timeline when articles are added
CREATE OR REPLACE FUNCTION auto_update_event_timeline()
RETURNS TRIGGER AS $$
BEGIN
    -- This would be implemented to automatically create timeline entries
    -- when new articles are associated with events
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 11. INSERT DEFAULT EVENT TYPES AND CATEGORIES
-- ============================================================================

-- Insert default event types
INSERT INTO events (event_name, event_type, event_category, event_description, is_ongoing) VALUES
('System Initialization', 'system', 'system', 'News Intelligence System initialization event', FALSE)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 12. GRANT PERMISSIONS
-- ============================================================================

-- Grant permissions to the database user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dockside_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dockside_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dockside_admin;

-- ============================================================================
-- 13. ADD COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE events IS 'Central table for tracking news events and their evolution over time';
COMMENT ON TABLE event_timeline_entries IS 'Tracks the timeline of events with chronological entries';
COMMENT ON TABLE entity_relationships IS 'Tracks relationships between entities across articles and events';
COMMENT ON TABLE event_clusters IS 'Groups similar events for analysis and summarization';
COMMENT ON TABLE context_tracking IS 'Stores contextual information and background for events';
COMMENT ON TABLE event_verification IS 'Tracks verification status and fact-checking for events';

COMMENT ON COLUMN articles.event_id IS 'Reference to the main event this article covers';
COMMENT ON COLUMN articles.location_entities IS 'JSONB array of location entities mentioned in the article';
COMMENT ON COLUMN articles.person_entities IS 'JSONB array of person entities mentioned in the article';
COMMENT ON COLUMN articles.organization_entities IS 'JSONB array of organization entities mentioned in the article';
COMMENT ON COLUMN articles.event_confidence IS 'Confidence score that this article belongs to the assigned event';

-- ============================================================================
-- 14. DISPLAY SCHEMA ENHANCEMENT SUMMARY
-- ============================================================================

-- Show all new tables
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename IN (
    'events',
    'event_timeline_entries',
    'entity_relationships',
    'event_clusters',
    'context_tracking',
    'event_verification'
)
ORDER BY tablename;

-- Show schema enhancement completion
SELECT 'Event tracking enhancement completed successfully!' as status;
