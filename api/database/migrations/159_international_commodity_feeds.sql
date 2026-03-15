-- Migration 159: International regulatory and central bank feeds for commodities
-- Gold, silver, platinum are globally traded; we watch major central banks, mints, and
-- regulatory announcements across major producers, importers, and trading hubs.
-- Insert only when feed_url not already present. Category 'Regulatory' for filtering.

INSERT INTO finance.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at, category)
SELECT v.feed_name, v.feed_url, v.is_active, v.fetch_interval_seconds, NOW(), v.category
FROM (VALUES
    ('ECB Press Releases', 'https://www.ecb.europa.eu/rss/press.html', true, 3600, 'Regulatory'),
    ('Bank of England News', 'https://www.bankofengland.co.uk/rss/news', true, 3600, 'Regulatory'),
    ('Bank of Canada News', 'https://www.bankofcanada.ca/utility/news/feed/', true, 3600, 'Regulatory'),
    ('Bank of Canada Press Releases', 'https://www.bankofcanada.ca/content_type/press-releases/feed/', true, 3600, 'Regulatory'),
    ('Swiss National Bank Press Releases', 'https://www.snb.ch/public/en/rss/pressrel', true, 3600, 'Regulatory')
) AS v(feed_name, feed_url, is_active, fetch_interval_seconds, category)
WHERE NOT EXISTS (SELECT 1 FROM finance.rss_feeds f WHERE f.feed_url = v.feed_url);
