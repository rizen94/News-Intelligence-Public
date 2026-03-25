-- Migration 202: Correct RSS URLs that fail due to wrong paths or retired endpoints (Mar 2026).
-- Complements 192: some URLs there were verified at the time but now 404, or paths were incorrect.
-- Idempotent: match on exact feed_url (or LIKE only where noted).

-- ---------------------------------------------------------------------------
-- finance
-- ---------------------------------------------------------------------------

-- SEC: `rss.xml` returns 403; canonical working feed uses `pressreleases.rss`.
UPDATE finance.rss_feeds
SET feed_url = 'https://www.sec.gov/news/pressreleases.rss'
WHERE feed_url = 'https://www.sec.gov/news/pressreleases/rss.xml';

-- FDIC: `/news/feed/` is 404; press releases syndicate via GovDelivery (same pattern as FDIC site links).
UPDATE finance.rss_feeds AS t
SET feed_url = 'https://public.govdelivery.com/topics/USFDIC_26/feed.rss'
WHERE feed_url = 'https://www.fdic.gov/news/feed/'
  AND NOT EXISTS (
    SELECT 1 FROM finance.rss_feeds o
    WHERE o.feed_url = 'https://public.govdelivery.com/topics/USFDIC_26/feed.rss' AND o.id <> t.id
  );

-- Treasury: `home.treasury.gov/rss/press-releases` is 404; no stable replacement XML verified in-repo.
-- Deactivate until an operator wires GovDelivery or a documented Treasury RSS endpoint.
UPDATE finance.rss_feeds
SET is_active = false
WHERE feed_url = 'https://home.treasury.gov/rss/press-releases';

-- Reuters Arc outbound feeds return 404 (public Arc endpoints retired).
UPDATE finance.rss_feeds
SET is_active = false
WHERE feed_url LIKE 'https://www.reuters.com/arc/outboundfeeds/v3/%';

-- ---------------------------------------------------------------------------
-- politics
-- ---------------------------------------------------------------------------

UPDATE politics.rss_feeds
SET is_active = false
WHERE feed_url LIKE 'https://www.reuters.com/arc/outboundfeeds/v3/%';

-- ---------------------------------------------------------------------------
-- medicine
-- ---------------------------------------------------------------------------

-- FDA: newsroom root `rss.xml` is 404; press-releases feed lives under about-fda/stay-informed.
UPDATE medicine.rss_feeds AS t
SET feed_url = 'https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml'
WHERE feed_url = 'https://www.fda.gov/news-events/fda-newsroom/rss.xml'
  AND NOT EXISTS (
    SELECT 1 FROM medicine.rss_feeds o
    WHERE o.feed_url = 'https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml'
      AND o.id <> t.id
  );

-- BMJ: `content/current.rss` is 404; no drop-in replacement verified for automated fetch here.
UPDATE medicine.rss_feeds
SET is_active = false
WHERE feed_url = 'https://www.bmj.com/content/current.rss';

DO $$
BEGIN
  RAISE NOTICE 'Migration 202: RSS URL corrections applied (SEC, FDIC, Treasury deactivate, FDA path, Reuters Arc deactivate, BMJ deactivate)';
END $$;
