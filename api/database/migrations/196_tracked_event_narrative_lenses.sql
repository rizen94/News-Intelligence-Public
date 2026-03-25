-- Domain-agnostic narrative + per-domain lens text for intelligence.tracked_events.
-- Flow: one LLM pass writes global_narrative; lens passes read only that artifact (+ metadata).

ALTER TABLE intelligence.tracked_events
  ADD COLUMN IF NOT EXISTS global_narrative TEXT,
  ADD COLUMN IF NOT EXISTS narrative_lenses JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS global_narrative_version INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS global_narrative_updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS narrative_lenses_updated_at TIMESTAMPTZ;

COMMENT ON COLUMN intelligence.tracked_events.global_narrative IS
  'Cross-domain storyline for this event; domain-specific angles go in narrative_lenses.';
COMMENT ON COLUMN intelligence.tracked_events.narrative_lenses IS
  'JSON object: domain key -> lens text, e.g. {"politics":"...","finance":"..."}.';
