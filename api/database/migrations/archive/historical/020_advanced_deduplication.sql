-- Advanced Deduplication System Migration
-- Adds content hashing, duplicate tracking, and clustering support

-- Add content_hash column to articles table
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS author VARCHAR(255);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS deduplication_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS similarity_score NUMERIC(4,3);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS cluster_id INTEGER;

-- Create indexes for efficient duplicate detection
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_deduplication_status ON articles(deduplication_status);
CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_author ON articles(author);

-- Create duplicate_pairs table for tracking duplicate relationships
CREATE TABLE IF NOT EXISTS duplicate_pairs (
    id SERIAL PRIMARY KEY,
    article1_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    article2_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    similarity_score NUMERIC(4,3) NOT NULL,
    duplicate_type VARCHAR(50) NOT NULL, -- 'exact', 'near_exact', 'semantic', 'cross_source'
    confidence_score NUMERIC(4,3) NOT NULL,
    detection_method VARCHAR(100) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article1_id, article2_id)
);

-- Create indexes for duplicate_pairs
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_article1 ON duplicate_pairs(article1_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_article2 ON duplicate_pairs(article2_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_similarity ON duplicate_pairs(similarity_score);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_type ON duplicate_pairs(duplicate_type);
CREATE INDEX IF NOT EXISTS idx_duplicate_pairs_status ON duplicate_pairs(status);

-- Create article_clusters table for clustering results
CREATE TABLE IF NOT EXISTS article_clusters (
    id SERIAL PRIMARY KEY,
    cluster_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    similarity_score NUMERIC(4,3) NOT NULL,
    cluster_rank INTEGER, -- Rank within cluster (0 = centroid)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cluster_id, article_id)
);

-- Create indexes for article_clusters
CREATE INDEX IF NOT EXISTS idx_article_clusters_cluster_id ON article_clusters(cluster_id);
CREATE INDEX IF NOT EXISTS idx_article_clusters_article_id ON article_clusters(article_id);
CREATE INDEX IF NOT EXISTS idx_article_clusters_similarity ON article_clusters(similarity_score);

-- Create cluster_metadata table for cluster information
CREATE TABLE IF NOT EXISTS cluster_metadata (
    id SERIAL PRIMARY KEY,
    cluster_id INTEGER NOT NULL,
    centroid_title VARCHAR(500),
    centroid_content TEXT,
    cluster_size INTEGER NOT NULL,
    similarity_threshold NUMERIC(4,3) NOT NULL,
    storyline_suggestion VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cluster_id)
);

-- Create indexes for cluster_metadata
CREATE INDEX IF NOT EXISTS idx_cluster_metadata_cluster_id ON cluster_metadata(cluster_id);
CREATE INDEX IF NOT EXISTS idx_cluster_metadata_size ON cluster_metadata(cluster_size);

-- Create deduplication_log table for tracking deduplication operations
CREATE TABLE IF NOT EXISTS deduplication_log (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL, -- 'same_source_check', 'cross_source_check', 'clustering'
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    articles_processed INTEGER DEFAULT 0,
    duplicates_found INTEGER DEFAULT 0,
    clusters_created INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    status VARCHAR(20) DEFAULT 'completed', -- 'completed', 'failed', 'partial'
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for deduplication_log
CREATE INDEX IF NOT EXISTS idx_deduplication_log_operation ON deduplication_log(operation_type);
CREATE INDEX IF NOT EXISTS idx_deduplication_log_article ON deduplication_log(article_id);
CREATE INDEX IF NOT EXISTS idx_deduplication_log_status ON deduplication_log(status);
CREATE INDEX IF NOT EXISTS idx_deduplication_log_created_at ON deduplication_log(created_at);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS update_duplicate_pairs_updated_at ON duplicate_pairs;
CREATE TRIGGER update_duplicate_pairs_updated_at
    BEFORE UPDATE ON duplicate_pairs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_cluster_metadata_updated_at ON cluster_metadata;
CREATE TRIGGER update_cluster_metadata_updated_at
    BEFORE UPDATE ON cluster_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create function to generate content hash for existing articles
CREATE OR REPLACE FUNCTION generate_content_hashes_for_existing_articles()
RETURNS INTEGER AS $$
DECLARE
    article_record RECORD;
    content_hash VARCHAR(64);
    updated_count INTEGER := 0;
BEGIN
    -- Update articles that don't have content_hash
    FOR article_record IN 
        SELECT id, title, content 
        FROM articles 
        WHERE content_hash IS NULL 
        AND content IS NOT NULL 
        AND LENGTH(content) > 0
    LOOP
        -- Generate hash using title and content
        content_hash := encode(
            digest(
                LOWER(REGEXP_REPLACE(REGEXP_REPLACE(article_record.title || '|' || article_record.content, '\s+', ' ', 'g'), '[^\w\s]', '', 'g')),
                'sha256'
            ),
            'hex'
        );
        
        UPDATE articles 
        SET content_hash = content_hash
        WHERE id = article_record.id;
        
        updated_count := updated_count + 1;
    END LOOP;
    
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- Run the function to generate hashes for existing articles
SELECT generate_content_hashes_for_existing_articles() as articles_updated;

-- Create view for duplicate statistics
CREATE OR REPLACE VIEW duplicate_statistics AS
SELECT 
    duplicate_type,
    COUNT(*) as duplicate_count,
    AVG(similarity_score) as avg_similarity,
    MIN(similarity_score) as min_similarity,
    MAX(similarity_score) as max_similarity,
    COUNT(DISTINCT article1_id) as unique_articles_with_duplicates
FROM duplicate_pairs
WHERE status = 'active'
GROUP BY duplicate_type;

-- Create view for cluster statistics
CREATE OR REPLACE VIEW cluster_statistics AS
SELECT 
    cm.cluster_id,
    cm.centroid_title,
    cm.cluster_size,
    cm.similarity_threshold,
    cm.storyline_suggestion,
    COUNT(ac.article_id) as actual_articles,
    AVG(ac.similarity_score) as avg_similarity
FROM cluster_metadata cm
LEFT JOIN article_clusters ac ON cm.cluster_id = ac.cluster_id
GROUP BY cm.cluster_id, cm.centroid_title, cm.cluster_size, cm.similarity_threshold, cm.storyline_suggestion;

-- Add comments for documentation
COMMENT ON COLUMN articles.content_hash IS 'SHA256 hash of normalized content for duplicate detection';
COMMENT ON COLUMN articles.author IS 'Article author name for metadata comparison';
COMMENT ON COLUMN articles.deduplication_status IS 'Status of deduplication processing: pending, processed, duplicate, unique';
COMMENT ON COLUMN articles.similarity_score IS 'Similarity score with most similar article';
COMMENT ON COLUMN articles.cluster_id IS 'ID of cluster this article belongs to';

COMMENT ON TABLE duplicate_pairs IS 'Tracks duplicate relationships between articles';
COMMENT ON TABLE article_clusters IS 'Maps articles to their clusters';
COMMENT ON TABLE cluster_metadata IS 'Metadata about article clusters for storyline suggestions';
COMMENT ON TABLE deduplication_log IS 'Logs deduplication operations and performance metrics';
