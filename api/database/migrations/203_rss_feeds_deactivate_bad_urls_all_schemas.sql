-- Migration 203: Deactivate or fix RSS rows in every domain schema (not only politics/finance).
-- 202 targeted finance/politics by exact URL; clones and slight URL variants may still be active.

-- Reuters Arc outbound feeds (404)
UPDATE artificial_intelligence.rss_feeds
SET is_active = false
WHERE feed_url ILIKE '%reuters.com/arc/outboundfeeds%';

UPDATE politics_2.rss_feeds
SET is_active = false
WHERE feed_url ILIKE '%reuters.com/arc/outboundfeeds%';

UPDATE finance_2.rss_feeds
SET is_active = false
WHERE feed_url ILIKE '%reuters.com/arc/outboundfeeds%';

-- Legacy politics/finance: catch any variant (http, trailing slash, etc.)
UPDATE politics.rss_feeds
SET is_active = false
WHERE feed_url ILIKE '%reuters.com/arc/outboundfeeds%';

UPDATE finance.rss_feeds
SET is_active = false
WHERE feed_url ILIKE '%reuters.com/arc/outboundfeeds%';

-- AP News RSS host no longer resolves — deactivate (avoid duplicate Yahoo URL vs existing rows)
UPDATE politics.rss_feeds SET is_active = false WHERE feed_url ILIKE '%feeds.apnews.com%';
UPDATE politics_2.rss_feeds SET is_active = false WHERE feed_url ILIKE '%feeds.apnews.com%';

-- Google AI: old Blogger atom URL (404); canonical from migration 192
UPDATE artificial_intelligence.rss_feeds AS t
SET feed_url = 'https://blog.google/technology/ai/rss/'
WHERE feed_url ILIKE '%ai.googleblog.com%'
  AND NOT EXISTS (
    SELECT 1 FROM artificial_intelligence.rss_feeds o
    WHERE o.feed_url = 'https://blog.google/technology/ai/rss/' AND o.id <> t.id
  );

-- The Blaze / C-SPAN: dead feeds (migration 192 deactivated in politics by id; catch by URL)
UPDATE politics.rss_feeds SET is_active = false WHERE feed_url ILIKE '%theblaze.com%feed%';
UPDATE politics.rss_feeds SET is_active = false WHERE feed_url ILIKE '%c-span.org/rss%';

-- Chronic HTTP 403/404 from automated fetch (operator may replace URLs later)
UPDATE finance.rss_feeds SET is_active = false WHERE feed_url ILIKE '%feeds.marketwatch.com%commodities%';
UPDATE finance.rss_feeds SET is_active = false WHERE feed_url ILIKE '%mining.com/feed%';
UPDATE medicine.rss_feeds SET is_active = false WHERE feed_url ILIKE '%jamanetwork.com/feeds%';
UPDATE politics.rss_feeds SET is_active = false WHERE feed_url ILIKE '%ft.com/rss%';

DO $$
BEGIN
  RAISE NOTICE 'Migration 203: RSS cleanup (all schemas) applied';
END $$;
