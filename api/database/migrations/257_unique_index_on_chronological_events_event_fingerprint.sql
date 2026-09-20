-- Create unique index on chronological_events (event_fingerprint, source_article_id) if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'chronological_events' AND indexname = 'ux_chronological_events_event_fingerprint_source_article_id') THEN
        CREATE UNIQUE INDEX ux_chronological_events_event_fingerprint_source_article_id
        ON public.chronological_events (event_fingerprint, source_article_id);
    END IF;
END $$;