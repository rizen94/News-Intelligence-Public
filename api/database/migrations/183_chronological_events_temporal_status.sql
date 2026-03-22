-- 183: Distinguish scheduled (event date after source article publication) vs occurred.
-- Values: unknown | occurred | scheduled

ALTER TABLE public.chronological_events
  ADD COLUMN IF NOT EXISTS temporal_status TEXT;

UPDATE public.chronological_events
SET temporal_status = 'unknown'
WHERE temporal_status IS NULL;

-- Backfill from source article published_at (first match across built-in domain article tables).
UPDATE public.chronological_events ce
SET temporal_status = CASE
  WHEN ce.actual_event_date IS NULL THEN 'unknown'
  WHEN COALESCE(
    (SELECT published_at FROM politics.articles WHERE id = ce.source_article_id LIMIT 1),
    (SELECT published_at FROM finance.articles WHERE id = ce.source_article_id LIMIT 1),
    (SELECT published_at FROM science_tech.articles WHERE id = ce.source_article_id LIMIT 1)
  ) IS NULL THEN 'unknown'
  WHEN ce.actual_event_date > (
    COALESCE(
      (SELECT published_at FROM politics.articles WHERE id = ce.source_article_id LIMIT 1),
      (SELECT published_at FROM finance.articles WHERE id = ce.source_article_id LIMIT 1),
      (SELECT published_at FROM science_tech.articles WHERE id = ce.source_article_id LIMIT 1)
    )::date
  ) THEN 'scheduled'
  ELSE 'occurred'
END;

ALTER TABLE public.chronological_events
  ALTER COLUMN temporal_status SET DEFAULT 'unknown';

ALTER TABLE public.chronological_events
  ALTER COLUMN temporal_status SET NOT NULL;

ALTER TABLE public.chronological_events
  DROP CONSTRAINT IF EXISTS chronological_events_temporal_status_check;

ALTER TABLE public.chronological_events
  ADD CONSTRAINT chronological_events_temporal_status_check
  CHECK (temporal_status IN ('unknown', 'occurred', 'scheduled'));

COMMENT ON COLUMN public.chronological_events.temporal_status IS
  'occurred: event date on/before source article publication date; scheduled: event date after publication; unknown: no date or no source article';
