-- Migration 267: Legal silo must not clone politics/finance/AI/medicine world feeds.
-- Those URLs consumed the RSS cycle and wrote into legal, so politics/finance starved.
-- Keep court/docket seeds (SCOTUSblog, ABA, Courthouse News, Federal Register, …).
--
-- Date: 2026-11-12

BEGIN;

UPDATE legal.rss_feeds
SET is_active = false,
    status = 'disabled',
    warning_message = 'Duplicate of a production-silo feed URL; legal ingest is court/docket sources only',
    updated_at = NOW()
WHERE is_active IS DISTINCT FROM false
  AND (
    feed_url IN (SELECT feed_url FROM politics.rss_feeds)
    OR feed_url IN (SELECT feed_url FROM finance.rss_feeds)
    OR feed_url IN (SELECT feed_url FROM artificial_intelligence.rss_feeds)
    OR feed_url IN (SELECT feed_url FROM medicine.rss_feeds)
  );

COMMIT;
