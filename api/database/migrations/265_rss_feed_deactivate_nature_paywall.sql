-- Migration 265: Deactivate Nature RSS feeds that never yield public HTML
--
-- Secondary (newsplatform-secondary) inline-fetches every RSS item. Nature
-- article URLs redirect to idp.nature.com/cookies_not_supported, so one cycle
-- stalls on Nature and other silos stop ingesting.
--
-- Evidence (Widow news_intel, 2026-11-12):
--   nature.com/nature/articles.rss — ~290 rows/silo, avg body ~500 chars, ~3% >800
--   nature.com/nclimate.rss        — 0 politics.articles
--   nature.com/nm.rss              — last_success 2026-09-09; recent bodies are
--                                    "preview of subscription content"
--
-- Date: 2026-11-12

BEGIN;

DO $$
DECLARE
  sch text;
  warn text := 'Nature article HTML is cookie/paywall (idp.nature.com cookies_not_supported); inline full-text fetch stalled newsplatform-secondary. Re-enable only if public HTML is available without login.';
BEGIN
  FOREACH sch IN ARRAY ARRAY[
    'artificial_intelligence',
    'medicine',
    'politics',
    'legal',
    'neurodiversity',
    'finance'
  ]
  LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = sch AND table_name = 'rss_feeds'
    ) THEN
      EXECUTE format(
        $sql$
        UPDATE %I.rss_feeds
        SET is_active = false,
            status = 'disabled',
            warning_message = %L,
            updated_at = NOW()
        WHERE is_active IS DISTINCT FROM false
          AND (
            feed_url ILIKE '%%nature.com/nature/articles.rss%%'
            OR feed_url ILIKE '%%nature.com/nm.rss%%'
            OR feed_url ILIKE '%%nature.com/nclimate.rss%%'
          )
        $sql$,
        sch,
        warn
      );
    END IF;
  END LOOP;
END $$;

COMMIT;
