-- Migration 253: Add quality_version for score provenance tracking
-- Part of quality scoring pipeline refactoring (quality_scoring_refactoring_plan.md)
-- Decouples RSS heuristic scores from deep analysis composite scores in articles.quality_score
-- 
-- Run on Widow (192.168.93.101):
--   psql -h 192.168.93.101 -p 6432 -U newsapp -d news_intel -f migrations/253_quality_score_provenance.sql

BEGIN;

-- =========================================================================
-- Step 1: Add provenance tracking column
-- =========================================================================
ALTER TABLE public.articles 
    ADD COLUMN IF NOT EXISTS quality_version TEXT DEFAULT 'rss_heuristic'
    CONSTRAINT valid_quality_version CHECK (quality_version IN ('rss_heuristic', 'deep_analysis'));

COMMENT ON COLUMN public.articles.quality_version IS 
    'Provenance of quality_score: rss_heuristic = RSS collector initial score; deep_analysis = post-enrichment composite';

-- =========================================================================
-- Step 2: Backfill existing rows with best-effort provenance detection
-- =========================================================================

-- Pass 1: Articles that clearly went through enrichment (analysis_results populated)
UPDATE public.articles SET quality_version = 'deep_analysis'
WHERE analysis_results IS NOT NULL 
      AND jsonb_array_length(analysis_results::jsonb) > 0;

-- Pass 2: Articles with extracted entities (entity extraction completed)
UPDATE public.articles SET quality_version = 'deep_analysis'
WHERE COALESCE(extracted_entities, '') != ''
  AND quality_version IS NULL;

-- Pass 3: Articles with analysis_updated_at set (analysis pipeline ran)
UPDATE public.articles SET quality_version = 'deep_analysis'
WHERE analysis_updated_at IS NOT NULL
  AND quality_version IS NULL;

-- Pass 4: Recent articles (updated in last 6 months, still unmarked)
-- heuristic: the scoring architecture that produces deep analysis scores
-- was active during this window; mark them conservatively
UPDATE public.articles SET quality_version = 'deep_analysis'
WHERE updated_at >= NOW() - INTERVAL '6 months'
  AND quality_version IS NULL;

-- Final safety net: anything still NULL gets the column default
UPDATE public.articles SET quality_version = COALESCE(quality_version, 'rss_heuristic')
WHERE quality_version IS NULL;

-- =========================================================================
-- Step 3: Verify results
-- =========================================================================
DO $$
DECLARE
    v_rss_count     bigint;
    v_deep_count    bigint;
    v_total         bigint;
BEGIN
    SELECT count(*) INTO v_total FROM public.articles;
    SELECT count(*) INTO v_rss_count FROM public.articles WHERE quality_version = 'rss_heuristic';
    SELECT count(*) INTO v_deep_count FROM public.articles WHERE quality_version = 'deep_analysis';
    
    RAISE NOTICE 'Migration 253 complete: total=%, rss_heuristic=%, deep_analysis=%',
        v_total, v_rss_count, v_deep_count;
END $$;

COMMIT;
