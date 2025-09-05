-- Fix database schema for v3.1.0
-- Connect to newsintelligence database

-- Check if articles table exists and fix column names
DO $$
BEGIN
    -- Check if articles table exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'articles') THEN
        -- Check if published_date column exists and rename it
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'articles' AND column_name = 'published_date') THEN
            ALTER TABLE articles RENAME COLUMN published_date TO published_at;
        END IF;
    ELSE
        -- Create articles table if it doesn't exist
        CREATE TABLE articles (
            id SERIAL PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            content TEXT,
            summary TEXT,
            url VARCHAR(1000),
            source VARCHAR(255),
            published_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category VARCHAR(100),
            tags TEXT[],
            sentiment_score FLOAT,
            entities JSONB,
            readability_score FLOAT,
            quality_score FLOAT
        );
    END IF;
END $$;

-- Create missing tables
CREATE TABLE IF NOT EXISTS story_targets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback_loop_status (
    id SERIAL PRIMARY KEY,
    is_running BOOLEAN DEFAULT false,
    last_run TIMESTAMP,
    stories_being_tracked INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fix RSS feeds table
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS last_success TIMESTAMP;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE rss_feeds ADD COLUMN IF NOT EXISTS error_count INTEGER DEFAULT 0;

-- Insert sample data
INSERT INTO story_targets (name, description, is_active) VALUES 
('Breaking News', 'High-impact breaking news stories', true),
('Technology', 'Technology and innovation stories', true),
('Politics', 'Political news and analysis', true)
ON CONFLICT DO NOTHING;

INSERT INTO feedback_loop_status (is_running, last_run, stories_being_tracked) VALUES 
(false, NOW() - INTERVAL '1 hour', 0)
ON CONFLICT DO NOTHING;

-- Insert sample RSS feeds
INSERT INTO rss_feeds (name, url, description, category, is_active, last_success) VALUES 
('BBC News', 'http://feeds.bbci.co.uk/news/rss.xml', 'BBC News RSS Feed', 'general', true, NOW()),
('TechCrunch', 'https://techcrunch.com/feed/', 'TechCrunch Technology News', 'technology', true, NOW()),
('Reuters', 'https://feeds.reuters.com/reuters/topNews', 'Reuters Top News', 'general', true, NOW())
ON CONFLICT DO NOTHING;

-- Insert sample articles
INSERT INTO articles (title, content, url, source, published_at, category) VALUES 
('AI Breakthrough in Medical Diagnosis', 'Scientists have developed a new AI system that can diagnose diseases with 95% accuracy. The system uses machine learning algorithms to analyze medical images and identify potential health issues.', 'https://example.com/ai-medical', 'BBC News', NOW() - INTERVAL '2 hours', 'technology'),
('Climate Change Summit Results', 'World leaders have reached a historic agreement on climate change at the latest summit. The agreement includes new targets for carbon emissions reduction.', 'https://example.com/climate-summit', 'Reuters', NOW() - INTERVAL '4 hours', 'politics'),
('New Space Mission Launched', 'NASA has successfully launched a new mission to explore Mars. The mission will study the planet''s atmosphere and search for signs of life.', 'https://example.com/space-mission', 'TechCrunch', NOW() - INTERVAL '6 hours', 'science')
ON CONFLICT DO NOTHING;

