-- Migration 248: Validated environment RSS into politics + URL fixes (Jun 2026).
-- Idempotent: skip inserts when feed_url exists; URL updates match exact old URL.

-- ---------------------------------------------------------------------------
-- politics: environment-climate spec feeds that validated (HTTP 200 + parseable)
-- Domain environment-climate is not pipeline-provisioned; route via politics silo.
-- ---------------------------------------------------------------------------

INSERT INTO politics.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at, category)
SELECT v.feed_name, v.feed_url, true, 3600, NOW(), 'Environment'
FROM (VALUES
    ('Carbon Brief', 'https://www.carbonbrief.org/feed'),
    ('Climate.gov', 'https://www.climate.gov/rss.xml'),
    ('E&E News', 'https://www.eenews.net/articles/feed/'),
    ('Guardian Environment', 'https://www.theguardian.com/environment/rss'),
    ('Nature Climate', 'https://www.nature.com/nclimate.rss')
) AS v(feed_name, feed_url)
WHERE NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o WHERE o.feed_url = v.feed_url
);

-- CSIS moved /analysis/feed → /rss.xml
UPDATE politics.rss_feeds AS t
SET feed_url = 'https://www.csis.org/rss.xml'
WHERE t.feed_url = 'https://www.csis.org/analysis/feed'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://www.csis.org/rss.xml' AND o.id <> t.id
  );

-- Politico path change
UPDATE politics.rss_feeds AS t
SET feed_url = 'https://rss.politico.com/politics-news.xml'
WHERE t.feed_url = 'https://www.politico.com/rss/politics08.xml'
  AND NOT EXISTS (
    SELECT 1 FROM politics.rss_feeds o
    WHERE o.feed_url = 'https://rss.politico.com/politics-news.xml' AND o.id <> t.id
  );

-- ---------------------------------------------------------------------------
-- artificial_intelligence
-- ---------------------------------------------------------------------------

UPDATE artificial_intelligence.rss_feeds AS t
SET feed_url = 'https://blog.langchain.com/rss/'
WHERE t.feed_url = 'https://blog.langchain.dev/rss/'
  AND NOT EXISTS (
    SELECT 1 FROM artificial_intelligence.rss_feeds o
    WHERE o.feed_url = 'https://blog.langchain.com/rss/' AND o.id <> t.id
  );

-- ---------------------------------------------------------------------------
-- medicine (align with migration 202 where row still has old URL)
-- ---------------------------------------------------------------------------

UPDATE medicine.rss_feeds AS t
SET feed_url = 'https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml',
    is_active = true
WHERE t.feed_url = 'https://www.fda.gov/news-events/fda-newsroom/rss.xml'
  AND NOT EXISTS (
    SELECT 1 FROM medicine.rss_feeds o
    WHERE o.feed_url = 'https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml'
      AND o.id <> t.id
  );

UPDATE medicine.rss_feeds AS t
SET feed_url = 'https://jamanetwork.com/rss/site_3/67.xml',
    is_active = true
WHERE t.feed_url = 'https://jamanetwork.com/feeds/journals/jama'
  AND NOT EXISTS (
    SELECT 1 FROM medicine.rss_feeds o
    WHERE o.feed_url = 'https://jamanetwork.com/rss/site_3/67.xml' AND o.id <> t.id
  );

DO $$
BEGIN
  RAISE NOTICE 'Migration 248: environment RSS seeds + URL fixes applied';
END $$;
