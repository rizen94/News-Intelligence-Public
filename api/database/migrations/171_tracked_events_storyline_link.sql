-- Migration 171: Add storyline_id to tracked_events
-- Bridges tracked_events (context-discovered) to storylines for synthesis.
-- Uses VARCHAR(255) to match chronological_events.storyline_id type.

ALTER TABLE intelligence.tracked_events
    ADD COLUMN IF NOT EXISTS storyline_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_tracked_events_storyline_id
    ON intelligence.tracked_events (storyline_id)
    WHERE storyline_id IS NOT NULL;
