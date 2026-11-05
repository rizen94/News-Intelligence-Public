-- Migration 251: Rescore keyword_score using new entity-match formula
-- Entity extraction path now scores proportionally from matched count:
--   1 match = 0.65, 2 = 0.73, 3 = 0.81, 4 = 0.89, 5+ ≈ 0.97 (capped)
-- Formula: kw_score = LEAST(0.97, 0.65 + (mc - 1) * 0.08) where mc = array length of matched_keywords
-- Idempotent — safe to run multiple times; always recomputes from source data.
-- Run: psql -h 192.168.93.101 -p 6432 -U newsapp -d news_intel -f migrations/251_entity_scoring_rescore.sql
-- Or:  python api/database/migrations/251_runner.py

BEGIN;

UPDATE public.storyline_article_suggestions
SET keyword_score = CASE
        WHEN matched_keywords IS NULL OR matched_keywords = '{}' THEN
            0.65
        ELSE LEAST(0.97, (0.65 + (cardinality(matched_keywords::text[]) - 1) * 0.08))::decimal(3,2)
    END;

-- Verify results:
-- SELECT keyword_score AS bucket, count(*) FROM public.storyline_article_suggestions GROUP BY keyword_score ORDER BY keyword_score;
-- SELECT min(keyword_score), max(keyword_score), avg(keyword_score) FROM public.storyline_article_suggestions;

COMMIT;
