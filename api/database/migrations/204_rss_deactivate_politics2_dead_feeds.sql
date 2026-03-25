-- Migration 204: Deactivate dead/403 feeds in politics + politics_2 (broader URL match than 203).

UPDATE politics.rss_feeds SET is_active = false WHERE feed_url ILIKE '%theblaze.com%';
UPDATE politics.rss_feeds SET is_active = false WHERE feed_url ILIKE '%c-span.org%rss%';
UPDATE politics.rss_feeds SET is_active = false WHERE feed_url ILIKE '%ft.com/rss%';

UPDATE politics_2.rss_feeds SET is_active = false WHERE feed_url ILIKE '%theblaze.com%';
UPDATE politics_2.rss_feeds SET is_active = false WHERE feed_url ILIKE '%c-span.org%rss%';
UPDATE politics_2.rss_feeds SET is_active = false WHERE feed_url ILIKE '%ft.com/rss%';

DO $$
BEGIN
  RAISE NOTICE 'Migration 204: politics_2 dead feeds deactivated';
END $$;
