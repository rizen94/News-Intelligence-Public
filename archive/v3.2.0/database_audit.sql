-- News Intelligence System v3.1.0 - Comprehensive Database Audit
-- Verifies schema integrity and query alignment

-- 1. Check all tables and their structures
\echo '=== DATABASE SCHEMA AUDIT ==='
\echo ''

\echo '1. ALL TABLES IN DATABASE:'
\dt

\echo ''
\echo '2. ARTICLES TABLE STRUCTURE:'
\d articles

\echo ''
\echo '3. STORY_CONSOLIDATIONS TABLE STRUCTURE:'
\d story_consolidations

\echo ''
\echo '4. RSS_FEEDS TABLE STRUCTURE:'
\d rss_feeds

\echo ''
\echo '5. STORY_TIMELINES TABLE STRUCTURE:'
\d story_timelines

\echo ''
\echo '6. AI_ANALYSIS TABLE STRUCTURE:'
\d ai_analysis

\echo ''
\echo '7. CHECKING FOR MISSING METRICS TABLES:'
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name LIKE '%metrics%';

\echo ''
\echo '8. CHECKING INDEXES:'
SELECT schemaname, tablename, indexname, indexdef 
FROM pg_indexes 
WHERE schemaname = 'public' 
ORDER BY tablename, indexname;

\echo ''
\echo '9. CHECKING FOREIGN KEY CONSTRAINTS:'
SELECT
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public';

\echo ''
\echo '10. CHECKING DATA TYPES CONSISTENCY:'
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name IN ('articles', 'story_consolidations', 'rss_feeds')
ORDER BY table_name, ordinal_position;

\echo ''
\echo '11. CHECKING FOR ORPHANED RECORDS:'
-- Check for articles without valid sources
SELECT 'Articles without valid sources:' as check_type, COUNT(*) as count
FROM articles 
WHERE source IS NULL OR source = '';

-- Check for story consolidations without timeline
SELECT 'Story consolidations without timeline:' as check_type, COUNT(*) as count
FROM story_consolidations 
WHERE story_timeline_id IS NULL;

\echo ''
\echo '12. CHECKING DATA INTEGRITY:'
-- Check for duplicate URLs
SELECT 'Duplicate URLs:' as check_type, COUNT(*) as count
FROM (
    SELECT url, COUNT(*) 
    FROM articles 
    WHERE url IS NOT NULL 
    GROUP BY url 
    HAVING COUNT(*) > 1
) duplicates;

-- Check for invalid timestamps
SELECT 'Invalid timestamps:' as check_type, COUNT(*) as count
FROM articles 
WHERE published_at > NOW() OR created_at > NOW();

\echo ''
\echo '=== DATABASE AUDIT COMPLETED ==='
