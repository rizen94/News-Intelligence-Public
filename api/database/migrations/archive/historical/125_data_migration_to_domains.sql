-- Migration 125: Data Migration to Domain Schemas
-- Migrates existing data from public schema to domain schemas
-- Created: December 7, 2025
-- Version: 4.0.3

-- ============================================================================
-- PHASE 2: DATA MIGRATION
-- ============================================================================

-- IMPORTANT: This migration assumes all existing data belongs to 'politics' domain
-- After migration, data can be recategorized as needed

-- ============================================================================
-- STEP 1: CATEGORIZE EXISTING FEEDS
-- ============================================================================

-- Add domain_key column to existing rss_feeds (temporary, for migration)
ALTER TABLE public.rss_feeds 
ADD COLUMN IF NOT EXISTS domain_key VARCHAR(50);

-- Categorize feeds based on feed_name (category column may not exist)
UPDATE public.rss_feeds 
SET domain_key = CASE
    WHEN feed_name ILIKE '%politic%' OR feed_name ILIKE '%government%' OR feed_name ILIKE '%election%' OR feed_name ILIKE '%congress%' OR feed_name ILIKE '%senate%' THEN 'politics'
    WHEN feed_name ILIKE '%finance%' OR feed_name ILIKE '%market%' OR feed_name ILIKE '%economy%' OR feed_name ILIKE '%business%' OR feed_name ILIKE '%stock%' OR feed_name ILIKE '%trading%' THEN 'finance'
    WHEN feed_name ILIKE '%tech%' OR feed_name ILIKE '%science%' OR feed_name ILIKE '%innovation%' OR feed_name ILIKE '%ai%' OR feed_name ILIKE '%software%' THEN 'science-tech'
    ELSE 'politics'  -- Default to politics for existing data
END
WHERE domain_key IS NULL;

-- ============================================================================
-- STEP 2: CATEGORIZE EXISTING ARTICLES
-- ============================================================================

-- Add domain_key column to existing articles (temporary, for migration)
ALTER TABLE public.articles 
ADD COLUMN IF NOT EXISTS domain_key VARCHAR(50);

-- Categorize articles based on their feed
UPDATE public.articles a
SET domain_key = COALESCE(f.domain_key, 'politics')
FROM public.rss_feeds f
WHERE a.feed_id = f.id
AND a.domain_key IS NULL;

-- For articles without matching feed, use source_domain analysis or default
UPDATE public.articles
SET domain_key = CASE
    WHEN source_domain ILIKE '%politic%' OR source_domain ILIKE '%gov%' OR source_domain ILIKE '%congress%' OR source_domain ILIKE '%senate%' THEN 'politics'
    WHEN source_domain ILIKE '%finance%' OR source_domain ILIKE '%market%' OR source_domain ILIKE '%business%' OR source_domain ILIKE '%stock%' OR source_domain ILIKE '%trading%' THEN 'finance'
    WHEN source_domain ILIKE '%tech%' OR source_domain ILIKE '%science%' OR source_domain ILIKE '%innovation%' THEN 'science-tech'
    ELSE 'politics'  -- Default to politics
END
WHERE domain_key IS NULL;

-- ============================================================================
-- STEP 3: MIGRATE ARTICLES TO DOMAIN SCHEMAS
-- ============================================================================

-- Migrate politics articles
INSERT INTO politics.articles 
SELECT * FROM public.articles 
WHERE domain_key = 'politics'
ON CONFLICT (id) DO NOTHING;

-- Migrate finance articles
INSERT INTO finance.articles 
SELECT * FROM public.articles 
WHERE domain_key = 'finance'
ON CONFLICT (id) DO NOTHING;

-- Migrate science-tech articles
INSERT INTO science_tech.articles 
SELECT * FROM public.articles 
WHERE domain_key = 'science-tech'
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STEP 4: MIGRATE TOPICS TO DOMAIN SCHEMAS
-- ============================================================================

-- Only migrate topics if the topics table exists in public schema
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'topics') THEN
        -- Migrate topics that are assigned to articles in each domain
        INSERT INTO politics.topics
        SELECT DISTINCT t.*
        FROM public.topics t
        WHERE t.id IN (
            SELECT DISTINCT ata.topic_id
            FROM public.article_topic_assignments ata
            JOIN public.articles a ON ata.article_id = a.id
            WHERE a.domain_key = 'politics'
        )
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO finance.topics
        SELECT DISTINCT t.*
        FROM public.topics t
        WHERE t.id IN (
            SELECT DISTINCT ata.topic_id
            FROM public.article_topic_assignments ata
            JOIN public.articles a ON ata.article_id = a.id
            WHERE a.domain_key = 'finance'
        )
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO science_tech.topics
        SELECT DISTINCT t.*
        FROM public.topics t
        WHERE t.id IN (
            SELECT DISTINCT ata.topic_id
            FROM public.article_topic_assignments ata
            JOIN public.articles a ON ata.article_id = a.id
            WHERE a.domain_key = 'science-tech'
        )
        ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- STEP 5: MIGRATE RSS FEEDS TO DOMAIN SCHEMAS
-- ============================================================================

-- Migrate politics feeds
INSERT INTO politics.rss_feeds
SELECT * FROM public.rss_feeds
WHERE domain_key = 'politics'
ON CONFLICT (id) DO NOTHING;

-- Migrate finance feeds
INSERT INTO finance.rss_feeds
SELECT * FROM public.rss_feeds
WHERE domain_key = 'finance'
ON CONFLICT (id) DO NOTHING;

-- Migrate science-tech feeds
INSERT INTO science_tech.rss_feeds
SELECT * FROM public.rss_feeds
WHERE domain_key = 'science-tech'
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STEP 6: MIGRATE STORYLINES TO DOMAIN SCHEMAS
-- ============================================================================

-- Migrate storylines based on their articles
INSERT INTO politics.storylines
SELECT DISTINCT s.*
FROM public.storylines s
WHERE s.id IN (
    SELECT DISTINCT sa.storyline_id
    FROM public.storyline_articles sa
    JOIN public.articles a ON sa.article_id = a.id
    WHERE a.domain_key = 'politics'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO finance.storylines
SELECT DISTINCT s.*
FROM public.storylines s
WHERE s.id IN (
    SELECT DISTINCT sa.storyline_id
    FROM public.storyline_articles sa
    JOIN public.articles a ON sa.article_id = a.id
    WHERE a.domain_key = 'finance'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO science_tech.storylines
SELECT DISTINCT s.*
FROM public.storylines s
WHERE s.id IN (
    SELECT DISTINCT sa.storyline_id
    FROM public.storyline_articles sa
    JOIN public.articles a ON sa.article_id = a.id
    WHERE a.domain_key = 'science-tech'
)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STEP 7: MIGRATE ARTICLE-TOPIC ASSIGNMENTS
-- ============================================================================

-- Migrate article-topic assignments (only if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'article_topic_assignments') THEN
        INSERT INTO politics.article_topic_assignments
        SELECT ata.*
        FROM public.article_topic_assignments ata
        JOIN public.articles a ON ata.article_id = a.id
        WHERE a.domain_key = 'politics'
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO finance.article_topic_assignments
        SELECT ata.*
        FROM public.article_topic_assignments ata
        JOIN public.articles a ON ata.article_id = a.id
        WHERE a.domain_key = 'finance'
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO science_tech.article_topic_assignments
        SELECT ata.*
        FROM public.article_topic_assignments ata
        JOIN public.articles a ON ata.article_id = a.id
        WHERE a.domain_key = 'science-tech'
        ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- STEP 8: MIGRATE STORYLINE ARTICLES
-- ============================================================================

-- Migrate politics storyline articles
INSERT INTO politics.storyline_articles
SELECT sa.*
FROM public.storyline_articles sa
JOIN public.articles a ON sa.article_id = a.id
WHERE a.domain_key = 'politics'
ON CONFLICT (storyline_id, article_id) DO NOTHING;

-- Migrate finance storyline articles
INSERT INTO finance.storyline_articles
SELECT sa.*
FROM public.storyline_articles sa
JOIN public.articles a ON sa.article_id = a.id
WHERE a.domain_key = 'finance'
ON CONFLICT (storyline_id, article_id) DO NOTHING;

-- Migrate science-tech storyline articles
INSERT INTO science_tech.storyline_articles
SELECT sa.*
FROM public.storyline_articles sa
JOIN public.articles a ON sa.article_id = a.id
WHERE a.domain_key = 'science-tech'
ON CONFLICT (storyline_id, article_id) DO NOTHING;

-- ============================================================================
-- STEP 9: MIGRATE TOPIC CLUSTERS
-- ============================================================================

-- Migrate topic clusters (only if tables exist)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'topic_clusters') THEN
        INSERT INTO politics.topic_clusters
        SELECT DISTINCT tc.*
        FROM public.topic_clusters tc
        WHERE tc.id IN (
            SELECT DISTINCT tcm.cluster_id
            FROM public.topic_cluster_memberships tcm
            JOIN politics.topics t ON tcm.topic_id = t.id
        )
        ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;

        INSERT INTO finance.topic_clusters
        SELECT DISTINCT tc.*
        FROM public.topic_clusters tc
        WHERE tc.id IN (
            SELECT DISTINCT tcm.cluster_id
            FROM public.topic_cluster_memberships tcm
            JOIN finance.topics t ON tcm.topic_id = t.id
        )
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO science_tech.topic_clusters
        SELECT DISTINCT tc.*
        FROM public.topic_clusters tc
        WHERE tc.id IN (
            SELECT DISTINCT tcm.cluster_id
            FROM public.topic_cluster_memberships tcm
            JOIN science_tech.topics t ON tcm.topic_id = t.id
        )
        ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- STEP 10: MIGRATE TOPIC CLUSTER MEMBERSHIPS
-- ============================================================================

-- Migrate memberships (only if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'topic_cluster_memberships') THEN
        INSERT INTO politics.topic_cluster_memberships
        SELECT tcm.*
        FROM public.topic_cluster_memberships tcm
        JOIN politics.topics t ON tcm.topic_id = t.id
        JOIN politics.topic_clusters tc ON tcm.cluster_id = tc.id
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO finance.topic_cluster_memberships
        SELECT tcm.*
        FROM public.topic_cluster_memberships tcm
        JOIN finance.topics t ON tcm.topic_id = t.id
        JOIN finance.topic_clusters tc ON tcm.cluster_id = tc.id
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO science_tech.topic_cluster_memberships
        SELECT tcm.*
        FROM public.topic_cluster_memberships tcm
        JOIN science_tech.topics t ON tcm.topic_id = t.id
        JOIN science_tech.topic_clusters tc ON tcm.cluster_id = tc.id
        ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- STEP 11: MIGRATE TOPIC LEARNING HISTORY
-- ============================================================================

-- Migrate learning history (only if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'topic_learning_history') THEN
        INSERT INTO politics.topic_learning_history
        SELECT tlh.*
        FROM public.topic_learning_history tlh
        JOIN politics.topics t ON tlh.topic_id = t.id
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO finance.topic_learning_history
        SELECT tlh.*
        FROM public.topic_learning_history tlh
        JOIN finance.topics t ON tlh.topic_id = t.id
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO science_tech.topic_learning_history
        SELECT tlh.*
        FROM public.topic_learning_history tlh
        JOIN science_tech.topics t ON tlh.topic_id = t.id
        ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- STEP 12: UPDATE DOMAIN METADATA
-- ============================================================================

-- Update domain metadata with counts
UPDATE domain_metadata dm
SET 
    article_count = (SELECT COUNT(*) FROM politics.articles),
    topic_count = (SELECT COUNT(*) FROM politics.topics),
    storyline_count = (SELECT COUNT(*) FROM politics.storylines),
    feed_count = (SELECT COUNT(*) FROM politics.rss_feeds),
    last_updated = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE dm.domain_id = (SELECT id FROM domains WHERE domain_key = 'politics');

UPDATE domain_metadata dm
SET 
    article_count = (SELECT COUNT(*) FROM finance.articles),
    topic_count = (SELECT COUNT(*) FROM finance.topics),
    storyline_count = (SELECT COUNT(*) FROM finance.storylines),
    feed_count = (SELECT COUNT(*) FROM finance.rss_feeds),
    last_updated = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE dm.domain_id = (SELECT id FROM domains WHERE domain_key = 'finance');

UPDATE domain_metadata dm
SET 
    article_count = (SELECT COUNT(*) FROM science_tech.articles),
    topic_count = (SELECT COUNT(*) FROM science_tech.topics),
    storyline_count = (SELECT COUNT(*) FROM science_tech.storylines),
    feed_count = (SELECT COUNT(*) FROM science_tech.rss_feeds),
    last_updated = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE dm.domain_id = (SELECT id FROM domains WHERE domain_key = 'science-tech');

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    politics_articles INTEGER;
    finance_articles INTEGER;
    science_tech_articles INTEGER;
    total_migrated INTEGER;
    public_articles INTEGER;
BEGIN
    -- Count migrated articles
    SELECT COUNT(*) INTO politics_articles FROM politics.articles;
    SELECT COUNT(*) INTO finance_articles FROM finance.articles;
    SELECT COUNT(*) INTO science_tech_articles FROM science_tech.articles;
    total_migrated := politics_articles + finance_articles + science_tech_articles;
    
    -- Count original articles
    SELECT COUNT(*) INTO public_articles FROM public.articles;
    
    RAISE NOTICE 'Migration Summary:';
    RAISE NOTICE '  Politics articles: %', politics_articles;
    RAISE NOTICE '  Finance articles: %', finance_articles;
    RAISE NOTICE '  Science-Tech articles: %', science_tech_articles;
    RAISE NOTICE '  Total migrated: %', total_migrated;
    RAISE NOTICE '  Original articles: %', public_articles;
    
    IF total_migrated = public_articles THEN
        RAISE NOTICE '✅ All articles migrated successfully';
    ELSE
        RAISE WARNING '⚠️  Article count mismatch: % migrated vs % original', total_migrated, public_articles;
    END IF;
END $$;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 125: Data migration to domain schemas complete';
    RAISE NOTICE 'Next: Verify data integrity and update API services';
END $$;

