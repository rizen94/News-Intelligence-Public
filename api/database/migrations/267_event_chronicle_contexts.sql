-- Migration 267: Indexed junction for event chronicle ↔ context links (P3)
-- Replaces LATERAL jsonb_array_elements(developments) anti-joins with btree lookup.
-- developments JSONB remains the display/history source of truth; this table is eligibility index.

CREATE TABLE IF NOT EXISTS intelligence.event_chronicle_contexts (
    context_id INTEGER PRIMARY KEY REFERENCES intelligence.contexts(id) ON DELETE CASCADE,
    event_id   INTEGER NOT NULL REFERENCES intelligence.tracked_events(id) ON DELETE CASCADE,
    linked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_chronicle_contexts_event_id
    ON intelligence.event_chronicle_contexts (event_id);

-- One-time backfill from existing chronicle developments
INSERT INTO intelligence.event_chronicle_contexts (context_id, event_id)
SELECT DISTINCT (dev->>'context_id')::int AS context_id, ec.event_id
FROM intelligence.event_chronicles ec,
     LATERAL jsonb_array_elements(ec.developments) AS dev
WHERE (dev->>'context_id') ~ '^[0-9]+$'
  AND EXISTS (
      SELECT 1 FROM intelligence.contexts c WHERE c.id = (dev->>'context_id')::int
  )
  AND EXISTS (
      SELECT 1 FROM intelligence.tracked_events te WHERE te.id = ec.event_id
  )
ON CONFLICT (context_id) DO NOTHING;

COMMENT ON TABLE intelligence.event_chronicle_contexts IS
  'Indexed context_id → event_id links for event_tracking eligibility (mirrors chronicle developments).';
