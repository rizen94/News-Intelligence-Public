-- v5.0 Phase 3: Story Entity Index for long-running story continuation matching.
-- Enables matching new events to dormant storylines across unbounded time windows.

CREATE TABLE IF NOT EXISTS story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    entity_name VARCHAR(255) NOT NULL,
    entity_role VARCHAR(100),
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
        'person', 'organization', 'location', 'case_number',
        'legislation_id', 'event', 'other'
    )),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    mention_count INTEGER DEFAULT 1,
    is_core_entity BOOLEAN DEFAULT FALSE,

    UNIQUE (storyline_id, entity_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_sei_entity_name ON story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_sei_storyline ON story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_sei_core ON story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_sei_entity_type ON story_entity_index (entity_type);
