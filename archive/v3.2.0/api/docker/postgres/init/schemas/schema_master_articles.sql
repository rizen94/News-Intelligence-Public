-- Master Articles Table for Enhanced Preprocessing
-- Stores consolidated articles from multiple sources

CREATE TABLE IF NOT EXISTS master_articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    summary TEXT,
    source VARCHAR(100) NOT NULL,
    sources JSONB NOT NULL, -- Array of source names
    source_count INTEGER NOT NULL DEFAULT 1,
    source_priority DECIMAL(3,2) DEFAULT 1.0, -- Higher for more sources
    category VARCHAR(100) DEFAULT 'General',
    published_at TIMESTAMP,
    url VARCHAR(1000),
    tags JSONB, -- Array of tag objects with text, type, score
    preprocessing_status VARCHAR(50) DEFAULT 'processed',
    consolidation_metadata JSONB, -- Metadata about consolidation process
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add master_article_id to articles table to link original articles
ALTER TABLE articles ADD COLUMN IF NOT EXISTS master_article_id INTEGER REFERENCES master_articles(id);

-- Add preprocessing_status to articles table
ALTER TABLE articles ADD COLUMN IF NOT EXISTS preprocessing_status VARCHAR(50);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_master_articles_source_count ON master_articles(source_count);
CREATE INDEX IF NOT EXISTS idx_master_articles_source_priority ON master_articles(source_priority);
CREATE INDEX IF NOT EXISTS idx_master_articles_category ON master_articles(category);
CREATE INDEX IF NOT EXISTS idx_master_articles_published_at ON master_articles(published_at);
CREATE INDEX IF NOT EXISTS idx_master_articles_preprocessing_status ON master_articles(preprocessing_status);
CREATE INDEX IF NOT EXISTS idx_articles_master_article_id ON articles(master_article_id);
CREATE INDEX IF NOT EXISTS idx_articles_preprocessing_status ON articles(preprocessing_status);

-- Create GIN index for JSONB columns
CREATE INDEX IF NOT EXISTS idx_master_articles_sources_gin ON master_articles USING GIN(sources);
CREATE INDEX IF NOT EXISTS idx_master_articles_tags_gin ON master_articles USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_master_articles_consolidation_metadata_gin ON master_articles USING GIN(consolidation_metadata);
