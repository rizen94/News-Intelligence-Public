-- Migration 293: story continuation recheck backoff on public.chronological_events.
-- Story continuation re-scanned the newest unlinked events every cycle, so events with
-- no viable storyline were re-verified indefinitely. These columns let the phase apply
-- exponential backoff per event instead. Idempotent.

ALTER TABLE public.chronological_events
  ADD COLUMN IF NOT EXISTS continuation_checked_at TIMESTAMPTZ;

ALTER TABLE public.chronological_events
  ADD COLUMN IF NOT EXISTS continuation_attempts INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.chronological_events.continuation_checked_at IS
  'Last story_continuation match attempt that did not auto-link this event.';
COMMENT ON COLUMN public.chronological_events.continuation_attempts IS
  'Consecutive story_continuation attempts without an auto-link; drives recheck backoff.';

-- Selection index for the unlinked pool: never-checked events first, then newest.
CREATE INDEX IF NOT EXISTS idx_chronological_events_continuation_pending
  ON public.chronological_events (continuation_checked_at NULLS FIRST, extraction_timestamp DESC)
  WHERE (storyline_id = '' OR storyline_id IS NULL) AND source_article_id IS NOT NULL;
