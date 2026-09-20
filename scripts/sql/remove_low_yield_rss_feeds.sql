-- Remove low-yield / low-quality RSS feeds (feed review 2026-07-07).
-- Run on Widow admin Postgres :5432 (not PgBouncer).
--
--   psql -h 127.0.0.1 -p 5432 -U newsapp -d news_intel -f scripts/sql/remove_low_yield_rss_feeds.sql
--
-- Existing articles keep their rows; rss_feed_id is left NULL where no FK blocks delete.
-- Review the preview CTE output before committing.

BEGIN;

-- ---------------------------------------------------------------------------
-- Preview: rows that match (run mentally before delete)
-- ---------------------------------------------------------------------------
SELECT 'legal' AS domain, id, feed_name FROM legal.rss_feeds
WHERE feed_name IN ('federalregister.gov — documents', 'jurist.org — feed')
UNION ALL
SELECT 'medicine', id, feed_name FROM medicine.rss_feeds
WHERE feed_name IN (
    'fda.gov — news-events', 'medrxiv.org — rss', 'nejm.org — action',
    'who.int — feeds', 'pubmed.ncbi.nlm.nih.gov — rss'
)
UNION ALL
SELECT 'artificial_intelligence', id, feed_name FROM artificial_intelligence.rss_feeds
WHERE feed_name IN (
    'AI News (Ben''s Bites)', 'Cohere Blog', 'Google Cloud AI Blog', 'Import AI Newsletter',
    'Interconnects', 'LangChain Blog', 'Lil''Log', 'Meta Engineering Blog', 'SemiAnalysis',
    'Stability AI News', 'distill.pub — rss.xml', 'hai.stanford.edu — news',
    'hai.stanford.edu — rss.xml', 'machinelearningmastery.com — blog', 'thegradient.pub — rss'
)
UNION ALL
SELECT 'politics', id, feed_name FROM politics.rss_feeds
WHERE feed_name IN (
    'Al Jazeera', 'BBC World', 'AP Top News', 'Carnegie Endowment', 'Chatham House',
    'Foreign Affairs', 'International Crisis Group', 'Lawfare', 'Politico', 'Reuters World'
)
UNION ALL
SELECT 'finance', id, feed_name FROM finance.rss_feeds
WHERE feed_name IN (
    'Yahoo Finance', 'MarketWatch Top Stories', 'Bank of Canada News',
    'Bank of Canada Press Releases', 'Kitco News Commodities', 'Kitco News Markets',
    'Kitco News Mining', 'MarketWatch Commodities', 'Reuters Business News',
    'Treasury Direct Announcements'
)
ORDER BY 1, 3;

-- ---------------------------------------------------------------------------
-- Deletes (by feed_name — safe across environments)
-- ---------------------------------------------------------------------------

DELETE FROM legal.rss_feeds
WHERE feed_name IN (
    'federalregister.gov — documents',
    'jurist.org — feed'
);

DELETE FROM medicine.rss_feeds
WHERE feed_name IN (
    'fda.gov — news-events',
    'medrxiv.org — rss',
    'nejm.org — action',
    'who.int — feeds',
    'pubmed.ncbi.nlm.nih.gov — rss'
);

DELETE FROM artificial_intelligence.rss_feeds
WHERE feed_name IN (
    'AI News (Ben''s Bites)',
    'Cohere Blog',
    'Google Cloud AI Blog',
    'Import AI Newsletter',
    'Interconnects',
    'LangChain Blog',
    'Lil''Log',
    'Meta Engineering Blog',
    'SemiAnalysis',
    'Stability AI News',
    'distill.pub — rss.xml',
    'hai.stanford.edu — news',
    'hai.stanford.edu — rss.xml',
    'machinelearningmastery.com — blog',
    'thegradient.pub — rss'
);

DELETE FROM politics.rss_feeds
WHERE feed_name IN (
    'Al Jazeera',
    'BBC World',
    'AP Top News',
    'Carnegie Endowment',
    'Chatham House',
    'Foreign Affairs',
    'International Crisis Group',
    'Lawfare',
    'Politico',
    'Reuters World'
);

-- Yahoo Finance articles (~1.9k low-quality rows); child rows CASCADE per domain FKs.
DELETE FROM finance.articles
WHERE rss_feed_id = (
    SELECT id FROM finance.rss_feeds WHERE feed_name = 'Yahoo Finance'
);

DELETE FROM finance.rss_feeds
WHERE feed_name IN (
    'Yahoo Finance',
    'MarketWatch Top Stories',
    'Bank of Canada News',
    'Bank of Canada Press Releases',
    'Kitco News Commodities',
    'Kitco News Markets',
    'Kitco News Mining',
    'MarketWatch Commodities',
    'Reuters Business News',
    'Treasury Direct Announcements'
);

COMMIT;

-- Post-check: remaining active feed counts per domain
SELECT 'legal' AS domain, COUNT(*) FILTER (WHERE is_active) AS active, COUNT(*) AS total FROM legal.rss_feeds
UNION ALL SELECT 'medicine', COUNT(*) FILTER (WHERE is_active), COUNT(*) FROM medicine.rss_feeds
UNION ALL SELECT 'artificial_intelligence', COUNT(*) FILTER (WHERE is_active), COUNT(*) FROM artificial_intelligence.rss_feeds
UNION ALL SELECT 'politics', COUNT(*) FILTER (WHERE is_active), COUNT(*) FROM politics.rss_feeds
UNION ALL SELECT 'finance', COUNT(*) FILTER (WHERE is_active), COUNT(*) FROM finance.rss_feeds
ORDER BY 1;
