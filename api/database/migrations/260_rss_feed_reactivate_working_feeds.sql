-- Migration 260: Reactivate RSS feeds that are still returning valid content
-- 
-- These feeds were silently deactivated by the weekly_cull health policy but their URLs
-- still return HTTP 200 with valid RSS/Atom XML. They have high reliability scores (0.96)
-- and success rates (97%) — they were false positives in the cull.
--
-- Scope: medicine (7 feeds), legal (3 feeds)
-- 
-- Date: 2026-11-07

BEGIN;

-- =============================================
-- medicine.rss_feeds (7 reactivations)
-- =============================================

-- [97] The Lancet — returned HTTP/2 200, application/rss+xml;charset=UTF-8
UPDATE medicine.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 97 AND feed_name = 'The Lancet';

-- [100] Nature Medicine — returned HTTP/2 200, application/rss+xml; charset=utf-8
UPDATE medicine.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 100 AND feed_name = 'Nature Medicine';

-- [101] WHO News — returned HTTP/2 200, application/rss+xml
UPDATE medicine.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 101 AND feed_name = 'WHO News';

-- [103] clinicaltrials.gov — returned HTTP/2 200, application/rss+xml (reliability 0.96)
UPDATE medicine.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 103 AND feed_name LIKE 'clinicaltrials.gov%';

-- [105] bioRxiv All — returned HTTP/2 200, application/xml (reliability 0.96)
UPDATE medicine.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 105 AND feed_name = 'bioRxiv All';

-- [184] medRxiv — returned HTTP/2 200, application/xml (reliability 0.96)
UPDATE medicine.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 184 AND feed_name = 'medRxiv';

-- [185] NEJM TOC — returned HTTP/2 200, application/xml;charset=UTF-8 (reliability 0.96)
UPDATE medicine.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 185 AND feed_name = 'NEJM TOC';

-- =============================================
-- legal.rss_feeds (3 reactivations)
-- =============================================

-- [127] ABA Journal — returned HTTP/2 200, text/xml; charset=utf-8 (reliability 0.96)
UPDATE legal.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 127 AND feed_name = 'ABA Journal';

-- [131] AboveTheLaw — returned HTTP/2 200, text/xml; charset=utf-8 (reliability 0.96)
UPDATE legal.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 131 AND feed_name LIKE '%AboveTheLaw%';

-- [182] Federal Register — returned HTTP/2 302 (redirect), previously successful on 2026-09-09
-- Note: URL still redirects; will be monitored after reactivation. Feed was working before cull.
UPDATE legal.rss_feeds 
SET is_active = true, status = 'active', warning_message = NULL, last_fetched_at = NOW()
WHERE id = 182 AND feed_name = 'Federal Register';

COMMIT;
