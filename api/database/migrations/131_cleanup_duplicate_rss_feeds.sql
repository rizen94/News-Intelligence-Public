-- Migration 131: Cleanup Duplicate RSS Feeds Across Domains
-- Removes feeds that exist in multiple domain schemas, keeping them in the correct domain
-- Created: January 2, 2026
-- Version: 4.0.4

-- ============================================================================
-- CLEANUP: Remove Duplicate Feeds from Wrong Domains
-- ============================================================================
-- Each RSS feed should exist in ONLY ONE domain schema.
-- This migration removes duplicates, keeping feeds in their correct domain.
-- ============================================================================

DO $$
DECLARE
    feed_record RECORD;
    correct_domain TEXT;
    wrong_domains TEXT[];
    domain_to_remove TEXT;
BEGIN
    -- Find feeds that exist in multiple domains and clean them up
    FOR feed_record IN
        SELECT 
            feed_name,
            feed_url,
            array_agg(DISTINCT schema_name ORDER BY schema_name) as domains
        FROM (
            SELECT 'politics' as schema_name, feed_name, feed_url FROM politics.rss_feeds
            UNION ALL
            SELECT 'finance' as schema_name, feed_name, feed_url FROM finance.rss_feeds
            UNION ALL
            SELECT 'science_tech' as schema_name, feed_name, feed_url FROM science_tech.rss_feeds
        ) all_feeds
        GROUP BY feed_name, feed_url
        HAVING COUNT(DISTINCT schema_name) > 1
    LOOP
        -- Determine correct domain based on feed name
        correct_domain := CASE
            -- Politics feeds
            WHEN feed_record.feed_name ILIKE '%politic%' 
                 OR feed_record.feed_name ILIKE '%government%'
                 OR feed_record.feed_name ILIKE '%election%'
                 OR feed_record.feed_name ILIKE '%congress%'
                 OR feed_record.feed_name ILIKE '%senate%'
                 OR feed_record.feed_name ILIKE '%white house%'
                 OR feed_record.feed_name ILIKE '%state department%'
                 OR feed_record.feed_name ILIKE '%justice department%'
                 OR feed_record.feed_name ILIKE '%defense department%'
                 OR feed_record.feed_name IN ('Associated Press Politics', 'CBC US Politics', 'Newsmax')
            THEN 'politics'
            
            -- Finance feeds
            WHEN feed_record.feed_name ILIKE '%finance%'
                 OR feed_record.feed_name ILIKE '%market%'
                 OR feed_record.feed_name ILIKE '%economy%'
                 OR feed_record.feed_name ILIKE '%business%'
                 OR feed_record.feed_name ILIKE '%stock%'
                 OR feed_record.feed_name ILIKE '%trading%'
                 OR feed_record.feed_name ILIKE '%SEC%'
                 OR feed_record.feed_name ILIKE '%Federal Reserve%'
                 OR feed_record.feed_name ILIKE '%Treasury%'
                 OR feed_record.feed_name ILIKE '%FDIC%'
            THEN 'finance'
            
            -- Science-Tech feeds
            WHEN feed_record.feed_name ILIKE '%tech%'
                 OR feed_record.feed_name ILIKE '%science%'
                 OR feed_record.feed_name ILIKE '%innovation%'
                 OR feed_record.feed_name ILIKE '%NASA%'
                 OR feed_record.feed_name ILIKE '%NIST%'
                 OR feed_record.feed_name ILIKE '%Energy Department%'
                 OR feed_record.feed_name ILIKE '%NIH%'
            THEN 'science_tech'
            
            -- Default: Keep in politics (most general news sources)
            ELSE 'politics'
        END;
        
        -- Get list of wrong domains (all domains except the correct one)
        SELECT ARRAY_AGG(domain_name) INTO wrong_domains
        FROM unnest(feed_record.domains) AS domain_name
        WHERE domain_name != correct_domain;
        
        -- Remove feed from wrong domains
        FOREACH domain_to_remove IN ARRAY wrong_domains
        LOOP
            RAISE NOTICE 'Removing feed "%" from % domain (keeping in % domain)', 
                feed_record.feed_name, domain_to_remove, correct_domain;
            
            -- Delete the feed from the wrong domain
            EXECUTE format('DELETE FROM %I.rss_feeds WHERE feed_name = $1 AND feed_url = $2', 
                domain_to_remove) 
            USING feed_record.feed_name, feed_record.feed_url;
        END LOOP;
    END LOOP;
    
    RAISE NOTICE 'Duplicate feed cleanup completed';
END $$;

-- ============================================================================
-- VERIFICATION: Check for remaining duplicates
-- ============================================================================

DO $$
DECLARE
    duplicate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO duplicate_count
    FROM (
        SELECT feed_name, feed_url
        FROM (
            SELECT 'politics' as schema_name, feed_name, feed_url FROM politics.rss_feeds
            UNION ALL
            SELECT 'finance' as schema_name, feed_name, feed_url FROM finance.rss_feeds
            UNION ALL
            SELECT 'science_tech' as schema_name, feed_name, feed_url FROM science_tech.rss_feeds
        ) all_feeds
        GROUP BY feed_name, feed_url
        HAVING COUNT(DISTINCT schema_name) > 1
    ) duplicates;
    
    IF duplicate_count > 0 THEN
        RAISE WARNING 'Still found % duplicate feeds after cleanup', duplicate_count;
    ELSE
        RAISE NOTICE '✅ No duplicate feeds found - cleanup successful';
    END IF;
END $$;

 