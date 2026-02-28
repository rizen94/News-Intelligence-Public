#!/bin/bash
# Script to check database schema for RSS feeds
# Run this after SSHing into the NAS

echo "🔍 Checking Database Schema for RSS Feeds"
echo "=========================================="
echo ""

# Check which schemas have rss_feeds tables
echo "1. Checking for rss_feeds tables in domain schemas..."
psql -d news_intelligence -c "
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_name = 'rss_feeds' 
AND table_schema IN ('finance', 'politics', 'science_tech')
ORDER BY table_schema;
"

echo ""
echo "2. Checking table structure (finance schema)..."
psql -d news_intelligence -c "\d finance.rss_feeds"

echo ""
echo "3. Current feed counts by domain..."
psql -d news_intelligence -c "
SELECT 'finance' as domain, COUNT(*) as feed_count FROM finance.rss_feeds
UNION ALL
SELECT 'politics', COUNT(*) FROM politics.rss_feeds
UNION ALL
SELECT 'science_tech', COUNT(*) FROM science_tech.rss_feeds;
"

echo ""
echo "4. Checking for existing official government feeds..."
psql -d news_intelligence -c "
SELECT 'finance' as domain, feed_name 
FROM finance.rss_feeds 
WHERE feed_name LIKE '%SEC%' OR feed_name LIKE '%Federal Reserve%' 
   OR feed_name LIKE '%Treasury%' OR feed_name LIKE '%FDIC%'
UNION ALL
SELECT 'politics', feed_name 
FROM politics.rss_feeds 
WHERE feed_name LIKE '%White House%' OR feed_name LIKE '%Department%' 
   OR feed_name LIKE '%Congressional%' OR feed_name LIKE '%GAO%' OR feed_name LIKE '%CBO%'
UNION ALL
SELECT 'science_tech', feed_name 
FROM science_tech.rss_feeds 
WHERE feed_name LIKE '%NASA%' OR feed_name LIKE '%NIST%' 
   OR feed_name LIKE '%Department of Energy%' OR feed_name LIKE '%NIH%';
"

echo ""
echo "5. Checking unique constraints on feed_url..."
psql -d news_intelligence -c "
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'finance' 
AND table_name = 'rss_feeds'
AND constraint_type IN ('UNIQUE', 'PRIMARY KEY');
"

echo ""
echo "✅ Schema check complete!"

