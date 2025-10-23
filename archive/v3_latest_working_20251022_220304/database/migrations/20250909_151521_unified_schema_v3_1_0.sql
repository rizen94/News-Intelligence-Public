-- Migration: unified_schema_v3_1_0
-- Generated: 2025-09-09T15:15:21.750278
-- Version: 3.1.0

-- Drop existing tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS storylines CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TABLE IF EXISTS rss_feeds CASCADE;

-- Create tables
CREATE TABLE rss_feeds (
    id integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name varchar(200) NOT NULL,
    url varchar(1000) NOT NULL,
    is_active boolean NOT NULL DEFAULT True,
    last_fetched timestamp,
    fetch_interval integer NOT NULL DEFAULT 300,
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error_count integer NOT NULL DEFAULT 0,
    last_error text
);

CREATE TABLE articles (
    id integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    title varchar(500) NOT NULL,
    content text,
    url varchar(1000),
    published_at timestamp,
    source varchar(200),
    category varchar(100),
    status varchar(50) NOT NULL DEFAULT 'pending',
    tags json,
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sentiment_score decimal(3,2),
    entities json,
    readability_score decimal(3,2),
    quality_score decimal(3,2) DEFAULT 0.0,
    summary text,
    ml_data json,
    language varchar(10) DEFAULT 'en',
    word_count integer DEFAULT 0,
    reading_time integer DEFAULT 0,
    feed_id integer
);

CREATE TABLE storylines (
    id integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    title varchar(300) NOT NULL,
    description text,
    status varchar(50) NOT NULL DEFAULT 'active',
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by varchar(100)
);

CREATE INDEX idx_articles_published_at ON articles (published_at);
CREATE INDEX idx_articles_source ON articles (source);
CREATE INDEX idx_articles_status ON articles (status);
CREATE INDEX idx_articles_category ON articles (category);
CREATE INDEX idx_articles_created_at ON articles (created_at);
CREATE INDEX idx_rss_feeds_active ON rss_feeds (is_active);
CREATE INDEX idx_rss_feeds_url ON rss_feeds (url);
CREATE INDEX idx_storylines_status ON storylines (status);
CREATE INDEX idx_storylines_created_at ON storylines (created_at);
ALTER TABLE articles ADD CONSTRAINT fk_articles_feed_id FOREIGN KEY (feed_id) REFERENCES rss_feeds(id);

-- Insert sample RSS feed
INSERT INTO rss_feeds (name, url, is_active, fetch_interval) VALUES
('Hacker News Test Feed', 'https://hnrss.org/frontpage', true, 300);

-- Insert sample articles
INSERT INTO articles (title, content, url, published_at, source, category, status, tags, quality_score, language, word_count, reading_time) VALUES
('Sample Article 1', 'This is sample content for testing.', 'https://example.com/1', NOW(), 'Hacker News Test Feed', 'Technology', 'processed', '["tech", "sample"]', 0.8, 'en', 50, 2),
('Sample Article 2', 'Another sample article for testing.', 'https://example.com/2', NOW(), 'Hacker News Test Feed', 'Technology', 'processed', '["tech", "sample"]', 0.7, 'en', 75, 3);