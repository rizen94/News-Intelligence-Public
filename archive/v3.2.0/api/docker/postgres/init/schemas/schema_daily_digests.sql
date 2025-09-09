-- Daily Digests Table for Living Story Narrator
-- Stores daily digest summaries of top stories

CREATE TABLE IF NOT EXISTS daily_digests (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    stories_included INTEGER DEFAULT 0,
    digest_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Digest Stories Junction Table
CREATE TABLE IF NOT EXISTS digest_stories (
    id SERIAL PRIMARY KEY,
    digest_id INTEGER REFERENCES daily_digests(id) ON DELETE CASCADE,
    story_id INTEGER REFERENCES master_articles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(digest_id, story_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_daily_digests_digest_date ON daily_digests(digest_date);
CREATE INDEX IF NOT EXISTS idx_daily_digests_created_at ON daily_digests(created_at);
CREATE INDEX IF NOT EXISTS idx_digest_stories_digest_id ON digest_stories(digest_id);
CREATE INDEX IF NOT EXISTS idx_digest_stories_story_id ON digest_stories(story_id);

-- Add unique constraint for one digest per day
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_digests_unique_date ON daily_digests(digest_date);
