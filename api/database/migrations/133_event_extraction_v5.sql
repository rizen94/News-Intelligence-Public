-- v5.0 Event Extraction Engine - Phase 1
-- Adds event fingerprinting and cross-source tracking columns to chronological_events,
-- and extends storylines with lifecycle status support.

-- Event fingerprint: normalized hash for cross-source deduplication
ALTER TABLE chronological_events
ADD COLUMN IF NOT EXISTS event_fingerprint VARCHAR(128),
ADD COLUMN IF NOT EXISTS canonical_event_id INTEGER REFERENCES chronological_events(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS source_count INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS last_corroborated_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS key_actors JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS outcome TEXT,
ADD COLUMN IF NOT EXISTS is_ongoing BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS continuation_signals JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS date_precision VARCHAR(20) DEFAULT 'unknown'
    CHECK (date_precision IN ('exact', 'week', 'month', 'quarter', 'year', 'unknown'));

CREATE INDEX IF NOT EXISTS idx_chrono_events_fingerprint ON chronological_events (event_fingerprint);
CREATE INDEX IF NOT EXISTS idx_chrono_events_canonical ON chronological_events (canonical_event_id);
CREATE INDEX IF NOT EXISTS idx_chrono_events_event_type ON chronological_events (event_type);
CREATE INDEX IF NOT EXISTS idx_chrono_events_actual_date ON chronological_events (actual_event_date);
CREATE INDEX IF NOT EXISTS idx_chrono_events_ongoing ON chronological_events (is_ongoing) WHERE is_ongoing = TRUE;
CREATE INDEX IF NOT EXISTS idx_chrono_events_storyline ON chronological_events (storyline_id);

-- Drop the old status constraint if it exists, then add the expanded one
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'storylines_status_check' AND table_name = 'storylines'
    ) THEN
        ALTER TABLE storylines DROP CONSTRAINT storylines_status_check;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_storyline_status'
    ) THEN
        ALTER TABLE storylines DROP CONSTRAINT chk_storyline_status;
    END IF;
END $$;

ALTER TABLE storylines
ADD CONSTRAINT chk_storyline_status CHECK (status IN (
    'draft', 'active', 'dormant', 'watching', 'concluded', 'archived', 'completed', 'failed'
));

ALTER TABLE storylines
ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS dormant_since TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS reactivation_count INTEGER DEFAULT 0;
