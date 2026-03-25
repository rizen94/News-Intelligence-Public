-- Migration 205: Update CBC RSS endpoints in politics_2 (old rss.cbc.ca endpoints retired)
-- Ensures active feed URLs use stable CBC webfeed endpoints.
-- Idempotent: only updates when target URL doesn't already exist; otherwise deactivates old row.

-- CBC world news
UPDATE politics_2.rss_feeds AS t
SET feed_url = 'https://www.cbc.ca/webfeed/rss/rss-world'
WHERE t.feed_url = 'https://rss.cbc.ca/rss/cbcworldnews.xml'
  AND NOT EXISTS (
    SELECT 1 FROM politics_2.rss_feeds o
    WHERE o.feed_url = 'https://www.cbc.ca/webfeed/rss/rss-world' AND o.id <> t.id
  );

UPDATE politics_2.rss_feeds
SET is_active = false
WHERE feed_url = 'https://rss.cbc.ca/rss/cbcworldnews.xml'
  AND EXISTS (
    SELECT 1 FROM politics_2.rss_feeds o
    WHERE o.feed_url = 'https://www.cbc.ca/webfeed/rss/rss-world'
  );

-- CBC top stories
UPDATE politics_2.rss_feeds AS t
SET feed_url = 'https://www.cbc.ca/webfeed/rss/rss-topstories'
WHERE t.feed_url = 'https://rss.cbc.ca/rss/topstories.xml'
  AND NOT EXISTS (
    SELECT 1 FROM politics_2.rss_feeds o
    WHERE o.feed_url = 'https://www.cbc.ca/webfeed/rss/rss-topstories' AND o.id <> t.id
  );

UPDATE politics_2.rss_feeds
SET is_active = false
WHERE feed_url = 'https://rss.cbc.ca/rss/topstories.xml'
  AND EXISTS (
    SELECT 1 FROM politics_2.rss_feeds o
    WHERE o.feed_url = 'https://www.cbc.ca/webfeed/rss/rss-topstories'
  );

DO $$
BEGIN
  RAISE NOTICE 'Migration 205: politics_2 CBC RSS URL updates applied';
END $$;

