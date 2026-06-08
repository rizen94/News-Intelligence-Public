-- Indexes for storyline_historical_context (entity facts + chronological spine lookups).

CREATE INDEX IF NOT EXISTS idx_versioned_facts_entity_valid_from
    ON intelligence.versioned_facts (entity_profile_id, valid_from DESC NULLS LAST)
    WHERE superseded_by_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_chronological_events_storyline_date
    ON public.chronological_events (storyline_id, actual_event_date ASC NULLS LAST)
    WHERE canonical_event_id IS NULL;

COMMENT ON INDEX intelligence.idx_versioned_facts_entity_valid_from IS
    'Fast per-entity fact timeline for storyline_historical_context (non-superseded facts).';

COMMENT ON INDEX public.idx_chronological_events_storyline_date IS
    'Storyline chronological spine reads (canonical events only).';

ALTER TABLE intelligence.storyline_states
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
