-- Migration 147: Performance tuning — drop unused indexes, add missing column
-- Based on log analysis from 2026-03-07 showing:
--   - 20+ indexes on politics.articles with 0 scans
--   - Missing analysis_updated_at column causing pipeline errors
--   - finance.article_topic_clusters missing index (531 seq scans, 2 idx scans)

BEGIN;

-- 1. Add the missing analysis_updated_at column that causes pipeline errors
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'politics' AND table_name = 'articles' AND column_name = 'analysis_updated_at'
    ) THEN
        ALTER TABLE politics.articles ADD COLUMN analysis_updated_at TIMESTAMPTZ;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'finance' AND table_name = 'articles' AND column_name = 'analysis_updated_at'
    ) THEN
        ALTER TABLE finance.articles ADD COLUMN analysis_updated_at TIMESTAMPTZ;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'science_tech' AND table_name = 'articles' AND column_name = 'analysis_updated_at'
    ) THEN
        ALTER TABLE science_tech.articles ADD COLUMN analysis_updated_at TIMESTAMPTZ;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'articles' AND column_name = 'analysis_updated_at'
    ) THEN
        ALTER TABLE public.articles ADD COLUMN analysis_updated_at TIMESTAMPTZ;
    END IF;
END $$;

-- 2. Drop unused indexes on politics.articles (all have 0 scans)
--    Keeping: pkey, url idx, title idx, status idx, created_at idx, content_hash idx, published idx
DROP INDEX IF EXISTS politics.articles_processing_stage_idx;
DROP INDEX IF EXISTS politics.articles_processing_status_idx;
DROP INDEX IF EXISTS politics.articles_published_at_idx;
DROP INDEX IF EXISTS politics.articles_publisher_idx;
DROP INDEX IF EXISTS politics.articles_quality_score_idx;
DROP INDEX IF EXISTS politics.articles_reading_time_minutes_idx;
DROP INDEX IF EXISTS politics.articles_rss_feed_id_idx;
DROP INDEX IF EXISTS politics.articles_source_domain_idx;
DROP INDEX IF EXISTS politics.articles_analysis_results_idx;
DROP INDEX IF EXISTS politics.articles_topics_idx;
DROP INDEX IF EXISTS politics.idx_politics_articles_content_hash;
DROP INDEX IF EXISTS politics.idx_politics_articles_created_status;
DROP INDEX IF EXISTS politics.idx_politics_articles_processing_status;
DROP INDEX IF EXISTS politics.idx_politics_articles_published_at;
DROP INDEX IF EXISTS politics.idx_politics_articles_quality_created;
DROP INDEX IF EXISTS politics.idx_politics_articles_source_created;
DROP INDEX IF EXISTS politics.idx_politics_articles_source_domain;
DROP INDEX IF EXISTS politics.politics_articles_dash_idx;
DROP INDEX IF EXISTS politics.articles_tags_idx;
DROP INDEX IF EXISTS politics.articles_article_uuid_idx;
DROP INDEX IF EXISTS politics.articles_categories_idx;
DROP INDEX IF EXISTS politics.articles_entities_idx;
DROP INDEX IF EXISTS politics.articles_keywords_idx;
DROP INDEX IF EXISTS politics.articles_language_code_idx;
DROP INDEX IF EXISTS politics.articles_metadata_idx;

-- 3. Add missing index on finance.article_topic_clusters (531 seq scans vs 2 idx scans)
CREATE INDEX IF NOT EXISTS idx_finance_atc_article_id
    ON finance.article_topic_clusters (article_id);

COMMIT;
