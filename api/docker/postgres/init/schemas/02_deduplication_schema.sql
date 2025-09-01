-- Deduplication Schema Updates
-- Add missing columns for deduplication service

-- Add status column to articles table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'status'
    ) THEN
        ALTER TABLE articles ADD COLUMN status VARCHAR(50) DEFAULT 'active';
    END IF;
END $$;

-- Add metadata column to articles table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE articles ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
END $$;

-- Add quality_score column to articles table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'quality_score'
    ) THEN
        ALTER TABLE articles ADD COLUMN quality_score DECIMAL(3,2) DEFAULT 0.5;
    END IF;
END $$;

-- Create index on status column for better performance
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);

-- Create index on quality_score column for better performance
CREATE INDEX IF NOT EXISTS idx_articles_quality_score ON articles(quality_score);

-- Update existing articles to have default status
UPDATE articles SET status = 'active' WHERE status IS NULL;

-- Update existing articles to have default quality_score
UPDATE articles SET quality_score = 0.5 WHERE quality_score IS NULL;

-- Update existing articles to have default metadata
UPDATE articles SET metadata = '{}' WHERE metadata IS NULL;
