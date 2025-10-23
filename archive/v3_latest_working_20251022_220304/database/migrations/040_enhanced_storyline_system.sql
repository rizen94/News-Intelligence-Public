-- Enhanced Storyline System Migration
-- Adds advanced storyline features for comprehensive story tracking

-- First, let's enhance the existing storylines table
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS master_summary TEXT;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS timeline_summary TEXT;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS key_entities JSONB;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS sentiment_trend JSONB;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS source_diversity JSONB;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS last_article_added TIMESTAMP;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_processed BOOLEAN DEFAULT FALSE;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_processing_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS rag_content JSONB;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Create storyline_articles table if it doesn't exist
CREATE TABLE IF NOT EXISTS storyline_articles (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by VARCHAR(255),
    relevance_score FLOAT,
    importance_score FLOAT,
    temporal_order INTEGER,
    notes TEXT,
    ml_analysis JSONB,
    UNIQUE(storyline_id, article_id)
);

-- Create storyline_events table for timeline events
CREATE TABLE IF NOT EXISTS storyline_events (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    event_title VARCHAR(500) NOT NULL,
    event_description TEXT,
    event_date TIMESTAMP,
    event_source VARCHAR(255),
    event_type VARCHAR(100),
    confidence_score FLOAT,
    location VARCHAR(255),
    key_entities JSONB,
    sentiment_score FLOAT,
    impact_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ml_processed BOOLEAN DEFAULT FALSE
);

-- Create storyline_sources table for external sources
CREATE TABLE IF NOT EXISTS storyline_sources (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    source_url TEXT,
    source_title VARCHAR(500),
    content TEXT,
    relevance_score FLOAT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

-- Create storyline_edit_log table for tracking changes
CREATE TABLE IF NOT EXISTS storyline_edit_log (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    edit_type VARCHAR(50) NOT NULL, -- 'article_added', 'summary_updated', 'ml_processed', etc.
    edit_description TEXT,
    edit_data JSONB,
    edited_by VARCHAR(255),
    edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_storyline_articles_storyline_id ON storyline_articles(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_articles_article_id ON storyline_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_storyline_events_storyline_id ON storyline_events(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_events_event_date ON storyline_events(event_date);
CREATE INDEX IF NOT EXISTS idx_storyline_sources_storyline_id ON storyline_sources(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_edit_log_storyline_id ON storyline_edit_log(storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_edit_log_edited_at ON storyline_edit_log(edited_at);

-- Function to update article count when articles are added/removed
CREATE OR REPLACE FUNCTION update_storyline_article_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE storylines 
        SET article_count = article_count + 1,
            last_article_added = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.storyline_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE storylines 
        SET article_count = article_count - 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.storyline_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update article count
DROP TRIGGER IF EXISTS update_storyline_article_count_trigger ON storyline_articles;
CREATE TRIGGER update_storyline_article_count_trigger
    AFTER INSERT OR DELETE ON storyline_articles
    FOR EACH ROW
    EXECUTE FUNCTION update_storyline_article_count();

-- Function to log storyline edits
CREATE OR REPLACE FUNCTION log_storyline_edit()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO storyline_edit_log (storyline_id, edit_type, edit_description, edit_data, edited_by)
    VALUES (
        NEW.id,
        'storyline_updated',
        'Storyline updated: ' || COALESCE(NEW.title, 'Untitled'),
        jsonb_build_object(
            'title', NEW.title,
            'description', NEW.description,
            'status', NEW.status,
            'master_summary', NEW.master_summary,
            'timeline_summary', NEW.timeline_summary
        ),
        COALESCE(NEW.created_by, 'system')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to log storyline edits
DROP TRIGGER IF EXISTS log_storyline_edit_trigger ON storylines;
CREATE TRIGGER log_storyline_edit_trigger
    AFTER UPDATE ON storylines
    FOR EACH ROW
    EXECUTE FUNCTION log_storyline_edit();
