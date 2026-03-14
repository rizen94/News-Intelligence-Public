-- Migration 148: Add more finance RSS feeds for commodities, markets, and disclosures
-- Feeds are public. Insert only when feed_url not already present.
-- Include category if the table has that column (NOT NULL in some schemas).

INSERT INTO finance.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at, category)
SELECT v.feed_name, v.feed_url, v.is_active, v.fetch_interval_seconds, NOW(), v.category
FROM (VALUES
    ('Kitco News Markets', 'https://www.kitco.com/news/category/markets/rss', true, 3600, 'Business'),
    ('Kitco News Commodities', 'https://www.kitco.com/news/category/commodities/rss', true, 3600, 'Business'),
    ('Kitco News Mining', 'https://www.kitco.com/news/category/mining/rss', true, 3600, 'Business'),
    ('Mining.com', 'https://www.mining.com/feed/', true, 3600, 'Business'),
    ('Reuters Business News', 'https://www.reuters.com/markets/rssFeed', true, 3600, 'Business'),
    ('MarketWatch Top Stories', 'https://feeds.marketwatch.com/marketwatch/topstories/', true, 3600, 'Business'),
    ('Bloomberg Markets', 'https://feeds.bloomberg.com/markets/news.rss', true, 3600, 'Business'),
    ('Yahoo Finance', 'https://finance.yahoo.com/news/rssindex', true, 3600, 'Business')
) AS v(feed_name, feed_url, is_active, fetch_interval_seconds, category)
WHERE NOT EXISTS (SELECT 1 FROM finance.rss_feeds f WHERE f.feed_url = v.feed_url);
