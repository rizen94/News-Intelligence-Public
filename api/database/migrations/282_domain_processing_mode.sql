-- Migration 282: domain processing_mode (corpus vs research band).
-- Corpus domains run intake / fact-check / index only; research domains also
-- run storyline / chemistry / narrative assembly.
-- Idempotent. Safe for local news_intel_dev; do NOT apply on Widow until v11 cutover.

ALTER TABLE public.domains
    ADD COLUMN IF NOT EXISTS processing_mode TEXT NOT NULL DEFAULT 'research';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'domains_processing_mode_check'
      AND conrelid = 'public.domains'::regclass
  ) THEN
    ALTER TABLE public.domains
      ADD CONSTRAINT domains_processing_mode_check
      CHECK (processing_mode IN ('corpus', 'research'));
  END IF;
END $$;

COMMENT ON COLUMN public.domains.processing_mode IS
  'corpus = intake/appraisal/index only; research = full storyline/chemistry band';

CREATE INDEX IF NOT EXISTS idx_domains_processing_mode
    ON public.domains (processing_mode);

DO $$
BEGIN
  RAISE NOTICE 'Migration 282: public.domains.processing_mode ensured';
END $$;
