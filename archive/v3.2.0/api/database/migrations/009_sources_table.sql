-- Migration 009: Sources Table
-- Creates the sources table for news source management

-- Sources table for news source management
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,
    description TEXT,
    language VARCHAR(10) DEFAULT 'en',
    country VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'active',
    article_count INTEGER DEFAULT 0,
    articles_today INTEGER DEFAULT 0,
    articles_this_week INTEGER DEFAULT 0,
    last_article_date TIMESTAMP,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    avg_response_time INTEGER DEFAULT 0,
    reliability_score DECIMAL(3,2) DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_sources_category ON sources(category);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_is_active ON sources(is_active);
CREATE INDEX IF NOT EXISTS idx_sources_article_count ON sources(article_count);
CREATE INDEX IF NOT EXISTS idx_sources_reliability_score ON sources(reliability_score);
CREATE INDEX IF NOT EXISTS idx_sources_created_at ON sources(created_at);
CREATE INDEX IF NOT EXISTS idx_sources_updated_at ON sources(updated_at);

-- Create trigger for updated_at timestamp
DROP TRIGGER IF EXISTS update_sources_updated_at ON sources;
CREATE TRIGGER update_sources_updated_at
    BEFORE UPDATE ON sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert some default sources
INSERT INTO sources (name, url, category, description, language, country, is_active) VALUES
('BBC News', 'https://www.bbc.com/news', 'news', 'British Broadcasting Corporation - International news', 'en', 'UK', true),
('CNN', 'https://www.cnn.com', 'news', 'Cable News Network - Breaking news and analysis', 'en', 'US', true),
('Reuters', 'https://www.reuters.com', 'news', 'International news agency', 'en', 'UK', true),
('TechCrunch', 'https://techcrunch.com', 'technology', 'Technology news and startup coverage', 'en', 'US', true),
('The Verge', 'https://www.theverge.com', 'technology', 'Technology, science, art, and culture', 'en', 'US', true),
('Ars Technica', 'https://arstechnica.com', 'technology', 'Technology news and analysis', 'en', 'US', true),
('Financial Times', 'https://www.ft.com', 'business', 'International business and financial news', 'en', 'UK', true),
('Bloomberg', 'https://www.bloomberg.com', 'business', 'Business and financial news', 'en', 'US', true),
('The Guardian', 'https://www.theguardian.com', 'news', 'British daily newspaper', 'en', 'UK', true),
('NPR', 'https://www.npr.org', 'news', 'National Public Radio - News and analysis', 'en', 'US', true)
ON CONFLICT (url) DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE sources IS 'Stores news sources with metadata and performance metrics';
COMMENT ON COLUMN sources.category IS 'Source category: news, technology, business, politics, sports, entertainment, science, health, world, local, other';
COMMENT ON COLUMN sources.status IS 'Current status: active, inactive, error, warning';
COMMENT ON COLUMN sources.reliability_score IS 'Overall reliability score (0.0-1.0) based on accuracy and consistency';
COMMENT ON COLUMN sources.success_rate IS 'Percentage of successful article collection attempts';
COMMENT ON COLUMN sources.avg_response_time IS 'Average response time in milliseconds';
