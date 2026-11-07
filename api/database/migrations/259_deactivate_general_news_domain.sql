-- 259_deactivate_general_news_domain.sql
-- Remove general_news from active domains per project design:
-- the pipeline is built for topic-segmented domain silos, not a generic catch-all.
-- This migration deactivates the domain entry and purges stale pending items.

BEGIN;

-- 1. Deactivate the domain so it drops out of iter_url_schema_pairs() / pipeline processing
UPDATE public.domains
   SET is_active = FALSE,
       updated_at  = CURRENT_TIMESTAMP
 WHERE schema_name = 'general_news';

-- 2. Purge stale articles from general_news schema (no topic value — legacy/accidental)
-- Total: 245 rows (241 enriched/pending + 4 failed)
DELETE FROM general_news.articles;

COMMIT;

