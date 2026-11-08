-- Migration 261: Mark RSS feeds as permanently inactive/deleted (URLs genuinely broken)
-- 
-- These feeds have URLs that return errors even with User-Agent headers, or fail to connect.
-- They were previously working and scored well (0.96 reliability), but the source sites no longer
-- serve RSS feeds at these URLs — likely due to site redesigns, API changes, or content shifts.
-- 
-- Scope: medicine (3 feeds), legal (2 feeds), neurodiversity (1 feed)
-- 
-- Date: 2026-11-07

BEGIN;

-- =============================================
-- medicine.rss_feeds (3 deactivations)
-- =============================================

-- [98] jamanetwork.com — returned HTTP/2 403 even with User-Agent header
-- JAMA Network likely blocks RSS scraping or changed their API endpoints
UPDATE medicine.rss_feeds 
SET is_active = false, status = 'disabled', warning_message = 'URL returns 403 (bot blocked) even with browser User-Agent — source site may have changed API'
WHERE id = 98 AND feed_name LIKE 'jamanetwork.com%';

-- [99] bmj.com — returned HTTP/2 403 even with User-Agent header
-- BMJ likely blocks automated RSS access; feed has never had a reliability score (never successfully fetched)
UPDATE medicine.rss_feeds 
SET is_active = false, status = 'disabled', warning_message = 'URL returns 403 (bot blocked) even with browser User-Agent — source site blocks automated access'
WHERE id = 99 AND feed_name LIKE 'bmj.com%';

-- [102] FDA Press Releases — returned HTTP/2 404, URL no longer exists
-- FDA may have moved or removed this RSS endpoint; check fda.gov for new RSS paths if needed
UPDATE medicine.rss_feeds 
SET is_active = false, status = 'deleted_url', warning_message = 'URL returns 404 — source site removed/changed the RSS endpoint'
WHERE id = 102 AND feed_name = 'FDA Press Releases';

-- =============================================
-- legal.rss_feeds (2 deactivations)
-- =============================================

-- [130] lexblog.com — returned HTTP/2 403 even with User-Agent header
-- LexBlog likely blocks RSS scraping at the root /feed/ path
UPDATE legal.rss_feeds 
SET is_active = false, status = 'disabled', warning_message = 'URL returns 403 (bot blocked) even with browser User-Agent'
WHERE id = 130 AND feed_name LIKE 'lexblog.com%';

-- [183] JURIST — returned HTTP/2 403 even with User-Agent header
-- JURIST likely blocks automated access to their feed endpoint
UPDATE legal.rss_feeds 
SET is_active = false, status = 'disabled', warning_message = 'URL returns 403 (bot blocked) even with browser User-Agent'
WHERE id = 183 AND feed_name = 'JURIST';

-- =============================================
-- neurodiversity.rss_feeds (1 deactivation)
-- =============================================

-- [223] Autism (SAGE) — connection failed on initial check, has never successfully fetched 
-- SAGE Publishing likely blocks automated access or changed their TOC RSS endpoint
UPDATE neurodiversity.rss_feeds 
SET is_active = false, status = 'disabled', warning_message = 'Connection failed/never fetched; source site may block automated RSS access'
WHERE id = 223 AND feed_name LIKE 'Autism (SAGE)%';

COMMIT;
