-- Storyline Management Schema for News Intelligence System v3.1.0
-- This schema supports temporal storyline tracking with ML analysis

-- Storylines table - Main storyline entities
CREATE TABLE IF NOT EXISTS storylines (
    id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    priority INTEGER DEFAULT 1, -- 1=low, 2=medium, 3=high, 4=critical
    category VARCHAR(100),
    tags TEXT[],
    master_summary TEXT, -- AI-generated master summary
    timeline_summary TEXT, -- AI-generated timeline of events
    key_entities JSONB, -- Extracted key entities across all articles
    sentiment_trend JSONB, -- Sentiment analysis over time
    source_diversity JSONB, -- Analysis of source coverage
    last_article_added TIMESTAMP,
    article_count INTEGER DEFAULT 0,
    ml_processed BOOLEAN DEFAULT FALSE,
    ml_processing_status VARCHAR(50) DEFAULT 'pending',
    rag_content JSONB, -- Additional RAG content from Wikipedia/GDELT
    metadata JSONB -- Additional metadata
);

-- Storyline Articles - Junction table linking articles to storylines
CREATE TABLE IF NOT EXISTS storyline_articles (
    id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    storyline_id VARCHAR(255) NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    article_id VARCHAR(255) NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by VARCHAR(255),
    relevance_score FLOAT, -- AI-calculated relevance to storyline
    importance_score FLOAT, -- AI-calculated importance within storyline
    temporal_order INTEGER, -- Order within the storyline timeline
    notes TEXT, -- User notes about this article's role
    ml_analysis JSONB, -- ML analysis specific to this article's role in storyline
    UNIQUE(storyline_id, article_id)
);

-- Storyline Events - Timeline events extracted from articles
CREATE TABLE IF NOT EXISTS storyline_events (
    id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    storyline_id VARCHAR(255) NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    event_title VARCHAR(500) NOT NULL,
    event_description TEXT,
    event_date TIMESTAMP,
    event_source VARCHAR(255), -- Which article this event came from
    event_type VARCHAR(100), -- e.g., 'announcement', 'development', 'reaction', 'analysis'
    confidence_score FLOAT, -- AI confidence in event extraction
    location VARCHAR(255),
    key_entities JSONB, -- Entities involved in this event
    sentiment_score FLOAT,
    impact_score FLOAT, -- AI-calculated impact of this event
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ml_processed BOOLEAN DEFAULT FALSE
);

-- Storyline Sources - External sources for RAG content
CREATE TABLE IF NOT EXISTS storyline_sources (
    id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    storyline_id VARCHAR(255) NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL, -- 'wikipedia', 'gdelt', 'manual'
    source_url TEXT,
    source_title VARCHAR(500),
    content TEXT,
    relevance_score FLOAT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_storylines_status ON storylines(status);
CREATE INDEX IF NOT EXISTS idx_storylines_created_at ON storylines(created_at);
CREATE INDEX IF NOT EXISTS idx_storylines_priority ON storylines(priority);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_storyline_id ON storyline_articles(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_article_id ON storyline_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_storyline_events_storyline_id ON storyline_events(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_events_event_date ON storyline_events(event_date);
CREATE INDEX IF NOT EXISTS idx_storyline_sources_storyline_id ON storyline_sources(storyline_id);

-- Update triggers for updated_at
CREATE OR REPLACE FUNCTION update_storyline_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_storylines_updated_at
    BEFORE UPDATE ON storylines
    FOR EACH ROW
    EXECUTE FUNCTION update_storyline_updated_at();

-- Function to update article count when articles are added/removed
CREATE OR REPLACE FUNCTION update_storyline_article_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE storylines 
        SET article_count = article_count + 1,
            last_article_added = CURRENT_TIMESTAMP
        WHERE id = NEW.storyline_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE storylines 
        SET article_count = article_count - 1
        WHERE id = OLD.storyline_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_storyline_article_count_trigger
    AFTER INSERT OR DELETE ON storyline_articles
    FOR EACH ROW
    EXECUTE FUNCTION update_storyline_article_count();


