-- Content Prioritization and Story Tracking System v4.0
-- This script adds advanced content management capabilities

-- Create content priority levels table
CREATE TABLE IF NOT EXISTS content_priority_levels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    priority_score INTEGER NOT NULL, -- Higher = more important
    color_hex VARCHAR(7) DEFAULT '#000000',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default priority levels
INSERT INTO content_priority_levels (name, description, priority_score, color_hex) VALUES
('critical', 'Critical stories requiring immediate attention', 100, '#FF0000'),
('high', 'High priority stories to track closely', 75, '#FF6600'),
('medium', 'Standard priority stories', 50, '#FFCC00'),
('low', 'Low priority, minimal tracking', 25, '#00CC00'),
('ignore', 'Content to avoid collecting', 0, '#999999')
ON CONFLICT (name) DO NOTHING;

-- Create story threads table
CREATE TABLE IF NOT EXISTS story_threads (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    status VARCHAR(50) DEFAULT 'active', -- active, resolved, archived
    user_created BOOLEAN DEFAULT FALSE,
    auto_generated BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_activity TIMESTAMP DEFAULT NOW()
);

-- Create story thread keywords for automatic detection
CREATE TABLE IF NOT EXISTS story_thread_keywords (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER REFERENCES story_threads(id) ON DELETE CASCADE,
    keyword VARCHAR(200) NOT NULL,
    keyword_type VARCHAR(50) DEFAULT 'exact', -- exact, phrase, semantic
    weight DECIMAL(3,2) DEFAULT 1.0, -- 0.0 to 1.0
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create user interest profiles
CREATE TABLE IF NOT EXISTS user_interest_profiles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) DEFAULT 'default', -- For future multi-user support
    profile_name VARCHAR(100) DEFAULT 'default',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create user interest rules
CREATE TABLE IF NOT EXISTS user_interest_rules (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES user_interest_profiles(id) ON DELETE CASCADE,
    rule_type VARCHAR(50) NOT NULL, -- keyword, source, category, entity, topic
    rule_value TEXT NOT NULL,
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    action VARCHAR(50) DEFAULT 'track', -- track, avoid, boost, suppress
    weight DECIMAL(3,2) DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create content priority assignments
CREATE TABLE IF NOT EXISTS content_priority_assignments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    thread_id INTEGER REFERENCES story_threads(id),
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    assigned_by VARCHAR(50) DEFAULT 'system', -- system, user, auto
    confidence_score DECIMAL(5,4) DEFAULT 1.0, -- 0.0 to 1.0
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create content collection rules
CREATE TABLE IF NOT EXISTS content_collection_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(200) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- source_filter, content_filter, priority_filter
    rule_conditions JSONB NOT NULL, -- Flexible rule definition
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    action VARCHAR(50) NOT NULL, -- collect, avoid, boost, suppress
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create RAG context requests
CREATE TABLE IF NOT EXISTS rag_context_requests (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER REFERENCES story_threads(id),
    request_type VARCHAR(50) NOT NULL, -- historical_context, related_stories, background_info
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    request_query TEXT NOT NULL,
    response_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    processing_time_ms INTEGER
);

-- Create content engagement tracking
CREATE TABLE IF NOT EXISTS content_engagement (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    thread_id INTEGER REFERENCES story_threads(id),
    engagement_type VARCHAR(50) NOT NULL, -- read, share, bookmark, comment, ignore
    user_id VARCHAR(100) DEFAULT 'default',
    engagement_data JSONB, -- Additional engagement metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create feed priority assignments
CREATE TABLE IF NOT EXISTS feed_priority_assignments (
    id SERIAL PRIMARY KEY,
    feed_id INTEGER REFERENCES rss_feeds(id) ON DELETE CASCADE,
    priority_level_id INTEGER REFERENCES content_priority_levels(id),
    collection_frequency INTEGER DEFAULT 3600, -- seconds between collections
    max_articles_per_collection INTEGER DEFAULT 50,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create content deprioritization rules
CREATE TABLE IF NOT EXISTS content_deprioritization_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(200) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- keyword_blacklist, source_blacklist, content_pattern
    rule_conditions JSONB NOT NULL,
    deprioritization_level INTEGER DEFAULT 0, -- How much to reduce priority
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_story_threads_priority ON story_threads(priority_level_id);
CREATE INDEX IF NOT EXISTS idx_story_threads_status ON story_threads(status);
CREATE INDEX IF NOT EXISTS idx_content_priority_article ON content_priority_assignments(article_id);
CREATE INDEX IF NOT EXISTS idx_content_priority_thread ON content_priority_assignments(thread_id);
CREATE INDEX IF NOT EXISTS idx_user_interest_rules_profile ON user_interest_rules(profile_id);
CREATE INDEX IF NOT EXISTS idx_content_engagement_article ON content_engagement(article_id);
CREATE INDEX IF NOT EXISTS idx_feed_priority_feed ON feed_priority_assignments(feed_id);

-- Create function to update story thread activity
CREATE OR REPLACE FUNCTION update_story_thread_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE story_threads 
    SET last_activity = NOW(), updated_at = NOW()
    WHERE id = NEW.thread_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for story thread activity
DROP TRIGGER IF EXISTS trigger_update_story_thread_activity ON content_priority_assignments;
CREATE TRIGGER trigger_update_story_thread_activity
    AFTER INSERT OR UPDATE ON content_priority_assignments
    FOR EACH ROW
    EXECUTE FUNCTION update_story_thread_activity();

-- Create function to calculate article priority score
CREATE OR REPLACE FUNCTION calculate_article_priority(
    article_title TEXT,
    article_content TEXT,
    article_source VARCHAR(200),
    article_category VARCHAR(100)
) RETURNS INTEGER AS $$
DECLARE
    priority_score INTEGER := 50; -- Default medium priority
    keyword_match_count INTEGER := 0;
    rule_match_count INTEGER := 0;
BEGIN
    -- Check keyword matches in story threads
    SELECT COUNT(*) INTO keyword_match_count
    FROM story_thread_keywords stk
    JOIN story_threads st ON stk.thread_id = st.id
    WHERE st.status = 'active'
    AND (
        LOWER(article_title) LIKE '%' || LOWER(stk.keyword) || '%'
        OR LOWER(article_content) LIKE '%' || LOWER(stk.keyword) || '%'
    );
    
    -- Check user interest rules
    SELECT COUNT(*) INTO rule_match_count
    FROM user_interest_rules uir
    JOIN user_interest_profiles uip ON uir.profile_id = uip.id
    WHERE uip.is_active = TRUE AND uir.is_active = TRUE
    AND (
        (uir.rule_type = 'keyword' AND (
            LOWER(article_title) LIKE '%' || LOWER(uir.rule_value) || '%'
            OR LOWER(article_content) LIKE '%' || LOWER(uir.rule_value) || '%'
        ))
        OR (uir.rule_type = 'source' AND LOWER(article_source) LIKE '%' || LOWER(uir.rule_value) || '%')
        OR (uir.rule_type = 'category' AND LOWER(article_category) LIKE '%' || LOWER(uir.rule_value) || '%')
    );
    
    -- Calculate priority based on matches
    IF keyword_match_count > 0 THEN
        priority_score := priority_score + (keyword_match_count * 10);
    END IF;
    
    IF rule_match_count > 0 THEN
        priority_score := priority_score + (rule_match_count * 15);
    END IF;
    
    -- Ensure priority is within bounds
    priority_score := GREATEST(0, LEAST(100, priority_score));
    
    RETURN priority_score;
END;
$$ LANGUAGE plpgsql;

-- Insert default content collection rules
INSERT INTO content_collection_rules (rule_name, rule_type, rule_conditions, priority_level_id, action) VALUES
('High Priority Keywords', 'content_filter', '{"keywords": ["breaking", "urgent", "crisis", "emergency"]}', 
 (SELECT id FROM content_priority_levels WHERE name = 'high'), 'boost'),
('Avoid Low Quality Sources', 'source_filter', '{"sources": ["clickbait", "spam"]}', 
 (SELECT id FROM content_priority_levels WHERE name = 'ignore'), 'avoid'),
('Technology Focus', 'category_filter', '{"categories": ["technology", "AI", "innovation"]}', 
 (SELECT id FROM content_priority_levels WHERE name = 'high'), 'boost')
ON CONFLICT DO NOTHING;

-- Insert default user interest profile
INSERT INTO user_interest_profiles (user_id, profile_name) VALUES ('default', 'default')
ON CONFLICT DO NOTHING;

-- Insert default user interest rules
INSERT INTO user_interest_rules (profile_id, rule_type, rule_value, priority_level_id, action) VALUES
((SELECT id FROM user_interest_profiles WHERE profile_name = 'default'), 'category', 'technology', 
 (SELECT id FROM content_priority_levels WHERE name = 'high'), 'track'),
((SELECT id FROM user_interest_profiles WHERE profile_name = 'default'), 'category', 'politics', 
 (SELECT id FROM content_priority_levels WHERE name = 'medium'), 'track'),
((SELECT id FROM user_interest_profiles WHERE profile_name = 'default'), 'keyword', 'AI', 
 (SELECT id FROM content_priority_levels WHERE name = 'high'), 'boost')
ON CONFLICT DO NOTHING;

-- Update existing articles with default priority
UPDATE articles 
SET deduplication_status = 'unique' 
WHERE deduplication_status IS NULL;

-- Log schema update
INSERT INTO system_logs (level, message, source, created_at) 
VALUES ('INFO', 'Content prioritization schema v4.0 applied successfully', 'schema_migration', NOW());

COMMIT;
