-- News Intelligence System v2.1.0 - ML Database Schema Enhancements
-- This script adds the necessary tables and columns for ML data processing

-- Add ML data column to articles table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'ml_data'
    ) THEN
        ALTER TABLE articles ADD COLUMN ml_data JSONB;
        RAISE NOTICE 'Added ml_data column to articles table';
    ELSE
        RAISE NOTICE 'ml_data column already exists in articles table';
    END IF;
END $$;

-- Add processing_status column to articles table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'articles' AND column_name = 'processing_status'
    ) THEN
        ALTER TABLE articles ADD COLUMN processing_status VARCHAR(50);
        RAISE NOTICE 'Added processing_status column to articles table';
    ELSE
        RAISE NOTICE 'processing_status column already exists in articles table';
    END IF;
END $$;

-- Create article_clusters table for content clustering
CREATE TABLE IF NOT EXISTS article_clusters (
    cluster_id SERIAL PRIMARY KEY,
    main_article_id INTEGER REFERENCES articles(id),
    article_ids INTEGER[] NOT NULL,
    size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    cluster_type VARCHAR(50),
    summary_data JSONB
);

-- Create index on article_clusters for better performance
CREATE INDEX IF NOT EXISTS idx_article_clusters_main_article ON article_clusters(main_article_id);
CREATE INDEX IF NOT EXISTS idx_article_clusters_created_at ON article_clusters(created_at);

-- Create ml_datasets table for ML dataset management
CREATE TABLE IF NOT EXISTS ml_datasets (
    dataset_id SERIAL PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL UNIQUE,
    filters JSONB,
    article_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on ml_datasets
CREATE INDEX IF NOT EXISTS idx_ml_datasets_name ON ml_datasets(dataset_name);
CREATE INDEX IF NOT EXISTS idx_ml_datasets_created_at ON ml_datasets(created_at);

-- Create ml_dataset_content table for storing dataset content
CREATE TABLE IF NOT EXISTS ml_dataset_content (
    content_id SERIAL PRIMARY KEY,
    dataset_id INTEGER REFERENCES ml_datasets(dataset_id) ON DELETE CASCADE,
    content JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index on ml_dataset_content
CREATE INDEX IF NOT EXISTS idx_ml_dataset_content_dataset ON ml_dataset_content(dataset_id);

-- Create intelligence_pipeline_results table for tracking pipeline execution
CREATE TABLE IF NOT EXISTS intelligence_pipeline_results (
    result_id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    duration_minutes DECIMAL(10,2),
    articles_processed INTEGER,
    clusters_created INTEGER,
    datasets_created INTEGER,
    steps_completed TEXT[],
    errors TEXT[],
    results_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index on intelligence_pipeline_results
CREATE INDEX IF NOT EXISTS idx_pipeline_results_created_at ON intelligence_pipeline_results(created_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_started_at ON intelligence_pipeline_results(started_at);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for ml_datasets table
DROP TRIGGER IF EXISTS update_ml_datasets_updated_at ON ml_datasets;
CREATE TRIGGER update_ml_datasets_updated_at
    BEFORE UPDATE ON ml_datasets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create function to get ML processing statistics
CREATE OR REPLACE FUNCTION get_ml_processing_stats()
RETURNS TABLE(
    total_articles BIGINT,
    ml_processed BIGINT,
    processing_errors BIGINT,
    processing_progress DECIMAL(5,2),
    clusters_count BIGINT,
    datasets_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_articles,
        COUNT(CASE WHEN processing_status = 'ml_processed' THEN 1 END)::BIGINT as ml_processed,
        COUNT(CASE WHEN processing_status = 'processing_error' THEN 1 END)::BIGINT as processing_errors,
        CASE 
            WHEN COUNT(*) > 0 THEN 
                ROUND((COUNT(CASE WHEN processing_status = 'ml_processed' THEN 1 END)::DECIMAL / COUNT(*)) * 100, 2)
            ELSE 0 
        END as processing_progress,
        (SELECT COUNT(*) FROM article_clusters)::BIGINT as clusters_count,
        (SELECT COUNT(*) FROM ml_datasets)::BIGINT as datasets_count
    FROM articles;
END;
$$ LANGUAGE plpgsql;

-- Create function to get recent processing activity
CREATE OR REPLACE FUNCTION get_recent_processing_activity(hours_back INTEGER DEFAULT 24)
RETURNS TABLE(
    article_id INTEGER,
    title TEXT,
    processing_status VARCHAR(50),
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.title,
        COALESCE(a.processing_status, 'unprocessed') as processing_status,
        COALESCE(a.updated_at, a.created_at) as updated_at
    FROM articles a
    WHERE COALESCE(a.updated_at, a.created_at) >= NOW() - INTERVAL '1 hour' * hours_back
    ORDER BY COALESCE(a.updated_at, a.created_at) DESC
    LIMIT 50;
END;
$$ LANGUAGE plpgsql;

-- Create function to get dataset statistics
CREATE OR REPLACE FUNCTION get_dataset_statistics(dataset_id_param INTEGER)
RETURNS TABLE(
    article_count BIGINT,
    total_words BIGINT,
    total_chars BIGINT,
    avg_quality DECIMAL(5,2),
    earliest_date TIMESTAMP,
    latest_date TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as article_count,
        SUM(COALESCE((content->>'word_count')::INTEGER, 0))::BIGINT as total_words,
        SUM(COALESCE((content->>'char_count')::INTEGER, 0))::BIGINT as total_chars,
        ROUND(AVG(COALESCE((content->>'quality_score')::DECIMAL, 0)), 2) as avg_quality,
        MIN(COALESCE((content->>'published_date')::TIMESTAMP, '1970-01-01'::TIMESTAMP)) as earliest_date,
        MAX(COALESCE((content->>'published_date')::TIMESTAMP, '1970-01-01'::TIMESTAMP)) as latest_date
    FROM ml_dataset_content mdc
    WHERE mdc.dataset_id = dataset_id_param;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions to the database user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dockside_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dockside_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dockside_admin;

-- Create indexes for better performance on existing columns
CREATE INDEX IF NOT EXISTS idx_articles_processing_status ON articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles(published_date);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);
CREATE INDEX IF NOT EXISTS idx_articles_updated_at ON articles(updated_at);

-- Add comments to tables for documentation
COMMENT ON TABLE article_clusters IS 'Stores clusters of similar articles for ML processing';
COMMENT ON TABLE ml_datasets IS 'Stores metadata about ML datasets';
COMMENT ON TABLE ml_dataset_content IS 'Stores the actual content of ML datasets';
COMMENT ON TABLE intelligence_pipeline_results IS 'Tracks execution results of intelligence processing pipeline';

COMMENT ON COLUMN articles.ml_data IS 'JSONB field containing ML processing results and metadata';
COMMENT ON COLUMN articles.processing_status IS 'Current status of ML processing for this article';

-- Insert sample data for testing (if tables are empty)
INSERT INTO ml_datasets (dataset_name, filters, article_count)
SELECT 'sample_dataset', '{"test": true}'::jsonb, 0
WHERE NOT EXISTS (SELECT 1 FROM ml_datasets WHERE dataset_name = 'sample_dataset');

-- Display table creation summary
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename IN ('article_clusters', 'ml_datasets', 'ml_dataset_content', 'intelligence_pipeline_results')
ORDER BY tablename;

-- Display function creation summary
SELECT 
    proname as function_name,
    prosrc as function_source
FROM pg_proc 
WHERE proname IN ('get_ml_processing_stats', 'get_recent_processing_activity', 'get_dataset_statistics')
ORDER BY proname;
