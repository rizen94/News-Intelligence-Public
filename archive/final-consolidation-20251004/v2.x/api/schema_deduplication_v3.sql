-- Advanced Deduplication System Schema Update v3.0
-- This script adds deduplication capabilities to the news intelligence system

-- Add deduplication columns to articles table
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS duplicate_of INTEGER REFERENCES articles(id);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS deduplication_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS normalized_content TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_similarity_score DECIMAL(5,4);

-- Create deduplication groups table
CREATE TABLE IF NOT EXISTS duplicate_groups (
    id SERIAL PRIMARY KEY,
    canonical_article_id INTEGER REFERENCES articles(id),
    duplicate_count INTEGER DEFAULT 0,
    similarity_score DECIMAL(5,4),
    group_type VARCHAR(20) DEFAULT 'content', -- 'content', 'semantic', 'entity'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create duplicate detection log table
CREATE TABLE IF NOT EXISTS duplicate_detection_log (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),
    duplicate_of_id INTEGER REFERENCES articles(id),
    detection_method VARCHAR(20), -- 'url', 'content_hash', 'semantic', 'entity'
    similarity_score DECIMAL(5,4),
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create content hash index for fast lookups
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_dedup_status ON articles(deduplication_status);
CREATE INDEX IF NOT EXISTS idx_articles_is_duplicate ON articles(is_duplicate);

-- Create function to update duplicate group counts
CREATE OR REPLACE FUNCTION update_duplicate_group_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.duplicate_of IS NOT NULL THEN
        UPDATE duplicate_groups 
        SET duplicate_count = duplicate_count + 1, updated_at = NOW()
        WHERE canonical_article_id = NEW.duplicate_of;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update duplicate group counts
DROP TRIGGER IF EXISTS trigger_update_duplicate_group_count ON articles;
CREATE TRIGGER trigger_update_duplicate_group_count
    AFTER INSERT OR UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_duplicate_group_count();

-- Create function to clean up orphaned duplicate groups
CREATE OR REPLACE FUNCTION cleanup_orphaned_duplicate_groups()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM duplicate_groups 
    WHERE canonical_article_id NOT IN (SELECT id FROM articles);
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Insert initial deduplication configuration
INSERT INTO system_config (key, value, description, created_at) 
VALUES 
    ('deduplication_enabled', 'true', 'Enable/disable deduplication system', NOW()),
    ('deduplication_semantic_threshold', '0.85', 'Semantic similarity threshold for duplicates', NOW()),
    ('deduplication_entity_threshold', '0.7', 'Entity overlap threshold for duplicates', NOW()),
    ('deduplication_batch_size', '50', 'Batch size for deduplication processing', NOW())
ON CONFLICT (key) DO UPDATE SET 
    value = EXCLUDED.value,
    updated_at = NOW();

-- Update existing articles to have deduplication status
UPDATE articles SET deduplication_status = 'completed' WHERE deduplication_status IS NULL;

-- Log schema update
INSERT INTO system_logs (level, message, source, created_at) 
VALUES ('INFO', 'Deduplication schema v3.0 applied successfully', 'schema_migration', NOW());

COMMIT;
