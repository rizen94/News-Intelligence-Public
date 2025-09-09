-- Phase 2: Story Consolidation and AI Analysis Database Schema
-- News Intelligence System v3.1.0

-- Story Timelines Table
CREATE TABLE IF NOT EXISTS story_timelines (
    id SERIAL PRIMARY KEY,
    story_id VARCHAR(255) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    status VARCHAR(50) DEFAULT 'developing' CHECK (status IN ('developing', 'breaking', 'concluded', 'monitoring')),
    sentiment VARCHAR(20) DEFAULT 'neutral' CHECK (sentiment IN ('positive', 'negative', 'neutral', 'mixed')),
    impact_level VARCHAR(20) DEFAULT 'medium' CHECK (impact_level IN ('low', 'medium', 'high', 'critical')),
    confidence_score DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    sources_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Timeline Events Table
CREATE TABLE IF NOT EXISTS timeline_events (
    id SERIAL PRIMARY KEY,
    story_timeline_id INTEGER REFERENCES story_timelines(id) ON DELETE CASCADE,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source VARCHAR(255) NOT NULL,
    confidence DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    event_type VARCHAR(20) DEFAULT 'development' CHECK (event_type IN ('initial', 'development', 'update', 'conclusion')),
    sentiment VARCHAR(20) DEFAULT 'neutral' CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    entities JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Story Consolidations Table
CREATE TABLE IF NOT EXISTS story_consolidations (
    id SERIAL PRIMARY KEY,
    story_timeline_id INTEGER REFERENCES story_timelines(id) ON DELETE CASCADE,
    headline TEXT NOT NULL,
    consolidated_summary TEXT NOT NULL,
    key_points JSONB DEFAULT '[]',
    professional_report TEXT,
    executive_summary TEXT,
    recommendations JSONB DEFAULT '[]',
    ai_analysis JSONB DEFAULT '{}',
    sources JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- AI Analysis Table
CREATE TABLE IF NOT EXISTS ai_analysis (
    id SERIAL PRIMARY KEY,
    story_timeline_id INTEGER REFERENCES story_timelines(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL, -- 'sentiment', 'entities', 'topics', 'credibility', 'bias'
    analysis_data JSONB NOT NULL,
    confidence DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    model_used VARCHAR(100),
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Story Sources Table
CREATE TABLE IF NOT EXISTS story_sources (
    id SERIAL PRIMARY KEY,
    story_timeline_id INTEGER REFERENCES story_timelines(id) ON DELETE CASCADE,
    source_name VARCHAR(255) NOT NULL,
    source_url TEXT,
    source_type VARCHAR(50) DEFAULT 'rss', -- 'rss', 'api', 'manual'
    reliability_score DECIMAL(3,2) DEFAULT 0.5 CHECK (reliability_score >= 0.0 AND reliability_score <= 1.0),
    last_checked TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Story Keywords/Topics Table
CREATE TABLE IF NOT EXISTS story_keywords (
    id SERIAL PRIMARY KEY,
    story_timeline_id INTEGER REFERENCES story_timelines(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    keyword_type VARCHAR(50) DEFAULT 'topic', -- 'topic', 'entity', 'location', 'person', 'organization'
    relevance_score DECIMAL(3,2) DEFAULT 0.0 CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0),
    ai_confidence DECIMAL(3,2) DEFAULT 0.0 CHECK (ai_confidence >= 0.0 AND ai_confidence <= 1.0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Story Relationships Table (for connecting related stories)
CREATE TABLE IF NOT EXISTS story_relationships (
    id SERIAL PRIMARY KEY,
    source_story_id INTEGER REFERENCES story_timelines(id) ON DELETE CASCADE,
    target_story_id INTEGER REFERENCES story_timelines(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) DEFAULT 'related', -- 'related', 'follows', 'contradicts', 'updates'
    strength DECIMAL(3,2) DEFAULT 0.5 CHECK (strength >= 0.0 AND strength <= 1.0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_story_id, target_story_id)
);

-- AI Processing Queue Table
CREATE TABLE IF NOT EXISTS ai_processing_queue (
    id SERIAL PRIMARY KEY,
    story_timeline_id INTEGER REFERENCES story_timelines(id) ON DELETE CASCADE,
    processing_type VARCHAR(50) NOT NULL, -- 'consolidation', 'analysis', 'summarization', 'timeline_update'
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_story_timelines_story_id ON story_timelines(story_id);
CREATE INDEX IF NOT EXISTS idx_story_timelines_status ON story_timelines(status);
CREATE INDEX IF NOT EXISTS idx_story_timelines_created_at ON story_timelines(created_at);
CREATE INDEX IF NOT EXISTS idx_timeline_events_story_id ON timeline_events(story_timeline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_timestamp ON timeline_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_type ON timeline_events(event_type);
CREATE INDEX IF NOT EXISTS idx_story_consolidations_story_id ON story_consolidations(story_timeline_id);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_story_id ON ai_analysis(story_timeline_id);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_type ON ai_analysis(analysis_type);
CREATE INDEX IF NOT EXISTS idx_story_sources_story_id ON story_sources(story_timeline_id);
CREATE INDEX IF NOT EXISTS idx_story_keywords_story_id ON story_keywords(story_timeline_id);
CREATE INDEX IF NOT EXISTS idx_story_keywords_type ON story_keywords(keyword_type);
CREATE INDEX IF NOT EXISTS idx_ai_processing_queue_status ON ai_processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_ai_processing_queue_priority ON ai_processing_queue(priority);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add updated_at triggers
CREATE TRIGGER update_story_timelines_updated_at 
    BEFORE UPDATE ON story_timelines 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_story_consolidations_updated_at 
    BEFORE UPDATE ON story_consolidations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for testing
INSERT INTO story_timelines (story_id, title, summary, status, sentiment, impact_level, confidence_score, sources_count) VALUES
('climate-summit-2024', 'Global Climate Summit 2024', 'International climate negotiations reach critical phase with new emissions targets', 'developing', 'positive', 'high', 0.92, 15),
('ai-regulation-tech', 'Tech Industry AI Regulation', 'Government announces new AI safety regulations affecting major tech companies', 'breaking', 'mixed', 'medium', 0.87, 8)
ON CONFLICT (story_id) DO NOTHING;

INSERT INTO timeline_events (story_timeline_id, event_id, timestamp, title, description, source, confidence, event_type, sentiment, entities) VALUES
(1, 'climate-summit-1', '2024-09-05T10:00:00Z', 'Summit Opens', 'World leaders gather for climate summit with ambitious goals', 'Reuters', 0.95, 'initial', 'positive', '["Climate Summit", "UN", "World Leaders"]'),
(1, 'climate-summit-2', '2024-09-05T14:30:00Z', 'New Emissions Targets', 'Major economies announce revised carbon reduction commitments', 'AP News', 0.88, 'development', 'positive', '["Emissions", "Carbon Reduction", "G7"]'),
(2, 'ai-regulation-1', '2024-09-05T09:00:00Z', 'Regulation Announcement', 'New AI safety framework unveiled by regulatory body', 'TechCrunch', 0.92, 'initial', 'neutral', '["AI Regulation", "Tech Companies", "Safety Framework"]')
ON CONFLICT (event_id) DO NOTHING;

INSERT INTO story_consolidations (story_timeline_id, headline, consolidated_summary, key_points, professional_report, executive_summary, recommendations, ai_analysis, sources) VALUES
(1, 'Climate Summit Reaches Historic Agreement on Emissions', 'After three days of intensive negotiations, world leaders have reached a landmark agreement on climate action, with major economies committing to more ambitious emissions targets and establishing a new global carbon trading system.', 
 '["New emissions targets 40% more ambitious than previous commitments", "Global carbon trading system established with 95% participation", "$500 billion climate finance fund created for developing nations", "Binding enforcement mechanisms with international oversight"]',
 'The 2024 Global Climate Summit has concluded with what many are calling the most significant climate agreement in history. The comprehensive deal includes unprecedented commitments from major economies, with the United States, European Union, and China all pledging to reduce emissions by 50% by 2030. The agreement also establishes a global carbon trading system that will allow countries to trade emissions credits, potentially reducing the overall cost of climate action by $2 trillion over the next decade.',
 'Historic climate agreement reached with 50% emissions reduction by 2030 and $500B climate fund.',
 '["Monitor implementation of new emissions targets", "Track progress on climate finance fund", "Analyze impact on carbon markets", "Follow up on enforcement mechanisms"]',
 '{"sentiment": "positive", "entities": ["Climate Summit", "UN", "G7", "G20", "Carbon Trading"], "topics": ["Climate Change", "International Relations", "Environmental Policy"], "credibility": 0.94, "bias": "neutral", "factCheck": 0.91}',
 '["Reuters", "AP News", "BBC", "CNN", "The Guardian"]')
ON CONFLICT DO NOTHING;

INSERT INTO ai_analysis (story_timeline_id, analysis_type, analysis_data, confidence, model_used, processing_time_ms) VALUES
(1, 'sentiment', '{"overall": "positive", "breakdown": {"positive": 0.65, "neutral": 0.25, "negative": 0.10}}', 0.94, 'llama3.1:8b', 1250),
(1, 'entities', '{"people": ["Greta Thunberg", "Antonio Guterres"], "organizations": ["UN", "G7", "G20"], "locations": ["New York", "Paris"], "topics": ["Climate Change", "Carbon Trading"]}', 0.91, 'llama3.1:8b', 2100),
(1, 'credibility', '{"score": 0.94, "factors": {"source_diversity": 0.95, "fact_checking": 0.92, "expert_consensus": 0.96}}', 0.94, 'llama3.1:8b', 800),
(2, 'sentiment', '{"overall": "mixed", "breakdown": {"positive": 0.30, "neutral": 0.50, "negative": 0.20}}', 0.87, 'llama3.1:8b', 1100)
ON CONFLICT DO NOTHING;

-- Update story_timelines with correct sources_count
UPDATE story_timelines SET sources_count = (
    SELECT COUNT(*) FROM story_sources WHERE story_timeline_id = story_timelines.id
) WHERE id IN (1, 2);

-- Insert sample sources
INSERT INTO story_sources (story_timeline_id, source_name, source_url, source_type, reliability_score, is_active) VALUES
(1, 'Reuters', 'https://reuters.com', 'rss', 0.95, true),
(1, 'AP News', 'https://apnews.com', 'rss', 0.93, true),
(1, 'BBC', 'https://bbc.com', 'rss', 0.94, true),
(1, 'CNN', 'https://cnn.com', 'rss', 0.89, true),
(1, 'The Guardian', 'https://theguardian.com', 'rss', 0.92, true),
(2, 'TechCrunch', 'https://techcrunch.com', 'rss', 0.88, true),
(2, 'Ars Technica', 'https://arstechnica.com', 'rss', 0.91, true),
(2, 'Wired', 'https://wired.com', 'rss', 0.90, true)
ON CONFLICT DO NOTHING;

-- Insert sample keywords
INSERT INTO story_keywords (story_timeline_id, keyword, keyword_type, relevance_score, ai_confidence) VALUES
(1, 'Climate Change', 'topic', 0.98, 0.95),
(1, 'Carbon Emissions', 'topic', 0.96, 0.93),
(1, 'UN', 'organization', 0.94, 0.97),
(1, 'G7', 'organization', 0.92, 0.95),
(1, 'Paris Agreement', 'topic', 0.89, 0.91),
(2, 'AI Regulation', 'topic', 0.97, 0.94),
(2, 'Tech Companies', 'organization', 0.95, 0.92),
(2, 'Safety Framework', 'topic', 0.93, 0.90)
ON CONFLICT DO NOTHING;

COMMIT;

