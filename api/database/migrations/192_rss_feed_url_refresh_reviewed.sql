-- Migration 192: Refresh RSS feed URLs / deactivate dead feeds (operator review, Mar 2026).
-- Uses id + feed_name pattern match so mis-numbered environments skip safely.
-- Idempotent: UPDATE only when name matches; INSERT uses WHERE NOT EXISTS.

-- ---------------------------------------------------------------------------
-- politics
-- ---------------------------------------------------------------------------

-- Use table alias + NOT EXISTS so unique(feed_url) is never violated (idempotent re-runs, shared URLs).
UPDATE politics.rss_feeds AS t
SET feed_url = 'https://www.japantimes.co.jp/feed/'
WHERE t.id = 3 AND t.feed_name ILIKE '%japan times%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://www.japantimes.co.jp/feed/' AND o.id <> t.id
  );

UPDATE politics.rss_feeds AS t
SET feed_url = 'https://news.yahoo.com/rss/'
WHERE t.id = 4 AND t.feed_name ILIKE '%associated press%' AND t.feed_name NOT ILIKE '%politic%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://news.yahoo.com/rss/' AND o.id <> t.id
  );

UPDATE politics.rss_feeds AS t
SET feed_url = 'https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=xml'
WHERE t.id = 5 AND t.feed_name ILIKE '%reuters%' AND t.feed_url ILIKE '%feeds.reuters.com%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=xml' AND o.id <> t.id
  );

UPDATE politics.rss_feeds AS t
SET feed_url = 'https://www.pbs.org/newshour/feeds/rss/headlines'
WHERE t.id = 7 AND t.feed_name ILIKE '%pbs%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://www.pbs.org/newshour/feeds/rss/headlines' AND o.id <> t.id
  );

-- USA Today: dedicated feed (Yahoo RSS is often already taken by another row — unique feed_url).
UPDATE politics.rss_feeds AS t
SET feed_url = 'https://rssfeeds.usatoday.com/usatoday-NewsTopStories'
WHERE t.id = 8 AND t.feed_name ILIKE '%usa today%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://rssfeeds.usatoday.com/usatoday-NewsTopStories' AND o.id <> t.id
  );

-- AP politics: distinct URL from id 4 / 8 (avoid duplicate Yahoo).
UPDATE politics.rss_feeds AS t
SET feed_url = 'https://feeds.npr.org/1001/rss.xml'
WHERE t.id = 10 AND t.feed_name ILIKE '%associated press%' AND t.feed_name ILIKE '%politic%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://feeds.npr.org/1001/rss.xml' AND o.id <> t.id
  );

UPDATE politics.rss_feeds
SET is_active = false
WHERE id = 11 AND feed_name ILIKE '%c-span%';

UPDATE politics.rss_feeds AS t
SET feed_url = 'http://rss.cnn.com/rss/cnn_allpolitics.rss'
WHERE t.id = 12 AND t.feed_name ILIKE '%cnn%' AND t.feed_name ILIKE '%politic%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'http://rss.cnn.com/rss/cnn_allpolitics.rss' AND o.id <> t.id
  );

UPDATE politics.rss_feeds AS t
SET
    feed_name = 'BBC UK Politics',
    feed_url = 'https://feeds.bbci.co.uk/news/politics/rss.xml'
WHERE t.id = 13 AND (t.feed_name ILIKE '%times%uk%' OR t.feed_name ILIKE '%the times%')
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://feeds.bbci.co.uk/news/politics/rss.xml' AND o.id <> t.id
  );

UPDATE politics.rss_feeds
SET is_active = false
WHERE id = 14 AND feed_name ILIKE '%blaze%';

UPDATE politics.rss_feeds
SET is_active = false
WHERE id = 15 AND (feed_name ILIKE '%financial times%' OR feed_name ILIKE '%ft %');

UPDATE politics.rss_feeds AS t
SET feed_url = 'https://www.reuters.com/arc/outboundfeeds/v3/politics/?outputType=xml'
WHERE t.id = 35 AND t.feed_name ILIKE '%reuters%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://www.reuters.com/arc/outboundfeeds/v3/politics/?outputType=xml' AND o.id <> t.id
  );

UPDATE politics.rss_feeds AS t
SET feed_url = 'https://rss.politico.com/politics-news.xml'
WHERE t.id = 36 AND t.feed_name ILIKE '%politico%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://rss.politico.com/politics-news.xml' AND o.id <> t.id
  );

UPDATE politics.rss_feeds AS t
SET feed_url = 'https://slate.com/feeds/all.rss'
WHERE t.id = 37 AND t.feed_name ILIKE '%slate%'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://slate.com/feeds/all.rss' AND o.id <> t.id
  );

-- Replacement for The Blaze (no longer has RSS)
INSERT INTO politics.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at, category)
SELECT 'Daily Caller', 'https://dailycaller.com/feed/', true, 3600, NOW(), 'General'
WHERE NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds WHERE feed_url = 'https://dailycaller.com/feed/'
);

-- ---------------------------------------------------------------------------
-- finance
-- ---------------------------------------------------------------------------

UPDATE finance.rss_feeds
SET feed_url = 'https://www.sec.gov/news/pressreleases/rss.xml'
WHERE id = 76 AND (feed_name ILIKE '%sec%' OR feed_url ILIKE '%sec.gov%');

UPDATE finance.rss_feeds
SET feed_url = 'https://home.treasury.gov/rss/press-releases'
WHERE id = 78 AND feed_name ILIKE '%treasury%';

UPDATE finance.rss_feeds
SET feed_url = 'https://www.fdic.gov/news/feed/'
WHERE id = 79 AND feed_name ILIKE '%fdic%';

UPDATE finance.rss_feeds
SET is_active = false
WHERE id IN (81, 82, 83) AND feed_name ILIKE '%kitco%';

INSERT INTO finance.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at, category)
SELECT 'MarketWatch Commodities', 'https://feeds.marketwatch.com/marketwatch/commodities/', true, 3600, NOW(), 'General'
WHERE NOT EXISTS (
    SELECT 1 FROM finance.rss_feeds WHERE feed_url = 'https://feeds.marketwatch.com/marketwatch/commodities/'
);

UPDATE finance.rss_feeds
SET feed_url = 'https://www.reuters.com/arc/outboundfeeds/v3/business/?outputType=xml'
WHERE id = 85 AND feed_name ILIKE '%reuters%';

-- ---------------------------------------------------------------------------
-- medicine
-- ---------------------------------------------------------------------------

-- PubMed: saved-search RSS (tune term in PubMed “Create RSS” if needed)
UPDATE medicine.rss_feeds
SET feed_url = 'https://pubmed.ncbi.nlm.nih.gov/rss/create/saved_searches/?term=medicine%5BMeSH+Major+Topic%5D&limit=100'
WHERE id = 95 AND (feed_name ILIKE '%pubmed%' OR feed_url ILIKE '%pubmed%');

UPDATE medicine.rss_feeds
SET feed_url = 'https://jamanetwork.com/feeds/journals/jama'
WHERE id = 98 AND feed_name ILIKE '%jama%';

UPDATE medicine.rss_feeds
SET feed_url = 'https://www.bmj.com/content/current.rss'
WHERE id = 99 AND feed_name ILIKE '%bmj%';

UPDATE medicine.rss_feeds
SET feed_url = 'https://www.fda.gov/news-events/fda-newsroom/rss.xml'
WHERE id = 102 AND feed_name ILIKE '%fda%';

UPDATE medicine.rss_feeds
SET feed_url = 'https://connect.medrxiv.org/medrxiv_xml.php'
WHERE id = 104 AND feed_name ILIKE '%medrxiv%';

UPDATE medicine.rss_feeds
SET feed_url = 'https://connect.biorxiv.org/biorxiv_xml.php?subject=all'
WHERE id = 105 AND feed_name ILIKE '%biorxiv%';

-- ---------------------------------------------------------------------------
-- artificial_intelligence
-- ---------------------------------------------------------------------------

UPDATE artificial_intelligence.rss_feeds
SET is_active = false
WHERE id = 113 AND feed_name ILIKE '%anthropic%';

UPDATE artificial_intelligence.rss_feeds
SET feed_url = 'https://blog.google/technology/ai/rss/'
WHERE id = 114 AND (feed_name ILIKE '%google%ai%' OR feed_name ILIKE '%google blog%');

UPDATE artificial_intelligence.rss_feeds
SET feed_url = 'https://hai.stanford.edu/rss.xml'
WHERE id = 119 AND feed_name ILIKE '%stanford%hai%';

DO $$
BEGIN
  RAISE NOTICE 'Migration 192: RSS feed URL refresh applied (verify ids vs SELECT id, feed_name FROM *.rss_feeds)';
END $$;
