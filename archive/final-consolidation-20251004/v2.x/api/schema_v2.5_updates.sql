-- News Intelligence System v2.5 - Schema Updates
-- This script adds missing columns and updates the database for v2.5 features

-- ============================================================================
-- 1. ADD MISSING COLUMNS TO ARTICLES TABLE
-- ============================================================================

-- Add quality_score column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'quality_score'
    ) THEN
        ALTER TABLE articles ADD COLUMN quality_score DECIMAL(5,3);
        RAISE NOTICE 'Added quality_score column to articles table';
    ELSE
        RAISE NOTICE 'quality_score column already exists in articles table';
    END IF;
END $$;

-- Add validation_status column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'validation_status'
    ) THEN
        ALTER TABLE articles ADD COLUMN validation_status VARCHAR(20);
        RAISE NOTICE 'Added validation_status column to articles table';
    ELSE
        RAISE NOTICE 'validation_status column already exists in articles table';
    END IF;
END $$;

-- Add content_hash column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'content_hash'
    ) THEN
        ALTER TABLE articles ADD COLUMN content_hash VARCHAR(64);
        RAISE NOTICE 'Added content_hash column to articles table';
    ELSE
        RAISE NOTICE 'content_hash column already exists in articles table';
    END IF;
END $$;

-- Add url_hash column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'url_hash'
    ) THEN
        ALTER TABLE articles ADD COLUMN url_hash VARCHAR(64);
        RAISE NOTICE 'Added url_hash column to articles table';
    ELSE
        RAISE NOTICE 'url_hash column already exists in articles table';
    END IF;
END $$;

-- Add detected_language column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'detected_language'
    ) THEN
        ALTER TABLE articles ADD COLUMN detected_language VARCHAR(10);
        RAISE NOTICE 'Added detected_language column to articles table';
    ELSE
        RAISE NOTICE 'detected_language column already exists in articles table';
    END IF;
END $$;

-- Add language_confidence column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'language_confidence'
    ) THEN
        ALTER TABLE articles ADD COLUMN language_confidence DECIMAL(5,2);
        RAISE NOTICE 'Added language_confidence column to articles table';
    ELSE
        RAISE NOTICE 'language_confidence column already exists in articles table';
    END IF;
END $$;

-- Add word_count column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'word_count'
    ) THEN
        ALTER TABLE articles ADD COLUMN word_count INTEGER;
        RAISE NOTICE 'Added word_count column to articles table';
    ELSE
        RAISE NOTICE 'word_count column already exists in articles table';
    END IF;
END $$;

-- Add sentence_count column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'sentence_count'
    ) THEN
        ALTER TABLE articles ADD COLUMN sentence_count INTEGER;
        RAISE NOTICE 'Added sentence_count column to articles table';
    ELSE
        RAISE NOTICE 'sentence_count column already exists in articles table';
    END IF;
END $$;

-- Add content_completeness_score column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'content_completeness_score'
    ) THEN
        ALTER TABLE articles ADD COLUMN content_completeness_score DECIMAL(5,2);
        RAISE NOTICE 'Added content_completeness_score column to articles table';
    ELSE
        RAISE NOTICE 'content_completeness_score column already exists in articles table';
    END IF;
END $$;

-- Add readability_score column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'readability_score'
    ) THEN
        ALTER TABLE articles ADD COLUMN readability_score DECIMAL(5,2);
        RAISE NOTICE 'Added readability_score column to articles table';
    ELSE
        RAISE NOTICE 'readability_score column already exists in articles table';
    END IF;
END $$;

-- Add extracted_keywords column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'extracted_keywords'
    ) THEN
        ALTER TABLE articles ADD COLUMN extracted_keywords TEXT[];
        RAISE NOTICE 'Added extracted_keywords column to articles table';
    ELSE
        RAISE NOTICE 'extracted_keywords column already exists in articles table';
    END IF;
END $$;

-- Add keyword_scores column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'keyword_scores'
    ) THEN
        ALTER TABLE articles ADD COLUMN keyword_scores JSONB;
        RAISE NOTICE 'Added keyword_scores column to articles table';
    ELSE
        RAISE NOTICE 'keyword_scores column already exists in articles table';
    END IF;
END $$;

-- Add duplicate_of column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'duplicate_of'
    ) THEN
        ALTER TABLE articles ADD COLUMN duplicate_of INTEGER REFERENCES articles(id);
        RAISE NOTICE 'Added duplicate_of column to articles table';
    ELSE
        RAISE NOTICE 'duplicate_of column already exists in articles table';
    END IF;
END $$;

-- Add is_duplicate column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'is_duplicate'
    ) THEN
        ALTER TABLE articles ADD COLUMN is_duplicate BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added is_duplicate column to articles table';
    ELSE
        RAISE NOTICE 'is_duplicate column already exists in articles table';
    END IF;
END $$;

-- Add canonical_url column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'canonical_url'
    ) THEN
        ALTER TABLE articles ADD COLUMN canonical_url VARCHAR(500);
        RAISE NOTICE 'Added canonical_url column to articles table';
    ELSE
        RAISE NOTICE 'canonical_url column already exists in articles table';
    END IF;
END $$;

-- ============================================================================
-- 2. CREATE MISSING INDEXES
-- ============================================================================

-- Create index on quality_score
CREATE INDEX IF NOT EXISTS idx_articles_quality_score ON articles(quality_score);

-- Create index on validation_status
CREATE INDEX IF NOT EXISTS idx_articles_validation_status ON articles(validation_status);

-- Create index on content_hash
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);

-- Create index on url_hash
CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash);

-- Create index on detected_language
CREATE INDEX IF NOT EXISTS idx_articles_detected_language ON articles(detected_language);

-- Create index on language_confidence
CREATE INDEX IF NOT EXISTS idx_articles_language_confidence ON articles(language_confidence);

-- Create index on word_count
CREATE INDEX IF NOT EXISTS idx_articles_word_count ON articles(word_count);

-- Create index on sentence_count
CREATE INDEX IF NOT EXISTS idx_articles_sentence_count ON articles(sentence_count);

-- Create index on content_completeness_score
CREATE INDEX IF NOT EXISTS idx_articles_content_completeness_score ON articles(content_completeness_score);

-- Create index on readability_score
CREATE INDEX IF NOT EXISTS idx_articles_readability_score ON articles(readability_score);

-- Create index on duplicate_of
CREATE INDEX IF NOT EXISTS idx_articles_duplicate_of ON articles(duplicate_of);

-- Create index on is_duplicate
CREATE INDEX IF NOT EXISTS idx_articles_is_duplicate ON articles(is_duplicate);

-- ============================================================================
-- 3. ADD COLUMN COMMENTS
-- ============================================================================

-- Add comments to new columns
COMMENT ON COLUMN articles.quality_score IS 'Overall quality score of the article content (0.0-1.0)';
COMMENT ON COLUMN articles.validation_status IS 'Status of quality validation (passed, warning, failed)';
COMMENT ON COLUMN articles.content_hash IS 'SHA-256 hash of article content for deduplication';
COMMENT ON COLUMN articles.url_hash IS 'SHA-256 hash of article URL for deduplication';
COMMENT ON COLUMN articles.detected_language IS 'Detected language of the article content';
COMMENT ON COLUMN articles.language_confidence IS 'Confidence score of language detection (0.0-1.0)';
COMMENT ON COLUMN articles.word_count IS 'Number of words in the article content';
COMMENT ON COLUMN articles.sentence_count IS 'Number of sentences in the article content';
COMMENT ON COLUMN articles.content_completeness_score IS 'Score indicating content completeness (0.0-1.0)';
COMMENT ON COLUMN articles.readability_score IS 'Flesch Reading Ease score for readability';
COMMENT ON COLUMN articles.extracted_keywords IS 'Array of extracted keywords from content';
COMMENT ON COLUMN articles.keyword_scores IS 'JSON object with keyword relevance scores';
COMMENT ON COLUMN articles.duplicate_of IS 'Reference to the original article if this is a duplicate';
COMMENT ON COLUMN articles.is_duplicate IS 'Boolean flag indicating if this article is a duplicate';
COMMENT ON COLUMN articles.canonical_url IS 'Canonical URL for the article (normalized)';

-- ============================================================================
-- 4. UPDATE EXISTING DATA
-- ============================================================================

-- Update existing articles with default values
UPDATE articles SET 
    quality_score = 0.5,
    validation_status = 'pending',
    is_duplicate = FALSE
WHERE quality_score IS NULL 
   OR validation_status IS NULL 
   OR is_duplicate IS NULL;

-- ============================================================================
-- 5. GRANT PERMISSIONS
-- ============================================================================

-- Grant permissions to the newsapp user
GRANT ALL PRIVILEGES ON TABLE articles TO newsapp;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Schema v2.5 updates completed successfully!';
    RAISE NOTICE 'Added columns: quality_score, validation_status, content_hash, url_hash, detected_language, language_confidence, word_count, sentence_count, content_completeness_score, readability_score, extracted_keywords, keyword_scores, duplicate_of, is_duplicate, canonical_url';
    RAISE NOTICE 'Created indexes for all new columns';
    RAISE NOTICE 'Added comprehensive column comments';
    RAISE NOTICE 'Updated existing data with default values';
    RAISE NOTICE 'All permissions granted to newsapp user';
END $$;
