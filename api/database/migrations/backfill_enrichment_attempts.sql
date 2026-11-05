-- =============================================================================
-- backfill_enrichment_attempts: Fix zero-attempt stuck articles
-- =============================================================================
-- Bug: Three is_false_enriched_body() demotion paths set enrichment_status = 'failed'
--      WITHOUT incrementing enrichment_attempts, creating infinite retry loops.
--
-- Affected locations (all now fixed in code):
--   #1  _enrich_articles_batch_parallel Phase 3 (line ~870) — parallel drain
--   #2  enrich_articles_batch sequential path  (line ~1141) — sequential drain
--   #3  fetch_full_content_for_article          (line ~1386) — on-demand UI
--
-- Result of bug: Articles at attempts=0 loop forever — re-fetched, immediately
--                re-demoted, re-fetched... never hitting the >=3 cutoff for
--                automatic escalation to 'inaccessible'.
--
-- Backfill fix: Bump all stuck articles (failed + 0 attempts) to attempt 1 so they get
--               one more real retry cycle before pruning.
-- =============================================================================

-- Step 1: Check how many affected rows exist per schema
-- SELECT count(*) FROM <schema>.articles
--  WHERE enrichment_status = 'failed'
--    AND COALESCE(enrichment_attempts, 0) = 0;

-- Step 2: Backfill — bump to attempt 1 (so they get one more retry cycle):
UPDATE articles
SET enrichment_attempts = COALESCE(enrichment_attempts, 0) + 1,
    updated_at = NOW()
WHERE enrichment_status = 'failed'
  AND COALESCE(enrichment_attempts, 0) = 0;

-- Step 3 (optional): For stale items (>30 days old), fast-track to attempt 3 → inaccessible:
-- UPDATE articles
-- SET enrichment_attempts = GREATEST(COALESCE(enrichment_attempts, 0), 2) + 1,
--     updated_at = NOW()
-- WHERE enrichment_status = 'failed'
--   AND COALESCE(enrichment_attempts, 0) = 0
--   AND created_at < NOW() - INTERVAL '30 days';

-- Active pipeline schemas requiring backfill run:
--   politics, artificial-intelligence, finance, medicine, legal, neurodiversity, environment-climate
-- =============================================================================

