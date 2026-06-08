-- Migration 232: Fix storyline_article_suggestions for per-domain silos.
--
-- The table lived in public with FKs to public.storylines/articles (empty stubs).
-- Domain data lives in politics/finance/etc. schemas — inserts failed silently.
-- Add domain_key, drop invalid FKs, enforce uniqueness per domain.

BEGIN;

ALTER TABLE public.storyline_article_suggestions
    ADD COLUMN IF NOT EXISTS domain_key VARCHAR(64);

UPDATE public.storyline_article_suggestions
SET domain_key = 'politics'
WHERE domain_key IS NULL;

ALTER TABLE public.storyline_article_suggestions
    ALTER COLUMN domain_key SET DEFAULT 'politics';

ALTER TABLE public.storyline_article_suggestions
    ALTER COLUMN domain_key SET NOT NULL;

ALTER TABLE public.storyline_article_suggestions
    DROP CONSTRAINT IF EXISTS storyline_article_suggestions_storyline_id_fkey;

ALTER TABLE public.storyline_article_suggestions
    DROP CONSTRAINT IF EXISTS storyline_article_suggestions_article_id_fkey;

ALTER TABLE public.storyline_article_suggestions
    DROP CONSTRAINT IF EXISTS storyline_article_suggestions_storyline_id_article_id_key;

ALTER TABLE public.storyline_article_suggestions
    ADD CONSTRAINT storyline_article_suggestions_domain_storyline_article_key
    UNIQUE (domain_key, storyline_id, article_id);

DROP INDEX IF EXISTS public.idx_storyline_article_suggestions_pending;
DROP INDEX IF EXISTS public.idx_storyline_article_suggestions_score;
DROP INDEX IF EXISTS public.idx_storyline_article_suggestions_storyline;

CREATE INDEX IF NOT EXISTS idx_storyline_suggestions_domain_pending
    ON public.storyline_article_suggestions (domain_key, suggested_at DESC)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_storyline_suggestions_domain_storyline
    ON public.storyline_article_suggestions (domain_key, storyline_id, status);

CREATE INDEX IF NOT EXISTS idx_storyline_suggestions_domain_score
    ON public.storyline_article_suggestions (domain_key, storyline_id, combined_score DESC);

DO $$
BEGIN
    RAISE NOTICE 'Migration 232: storyline_article_suggestions domain_key + FK fix applied';
END $$;

COMMIT;
