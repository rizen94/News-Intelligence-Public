-- 179: story_entity_index in each domain schema (v5 story continuation).
-- Migration 135 created the table in whatever schema was current; silo DBs need
-- politics / finance / science_tech copies with FK to that schema's storylines.

-- politics
CREATE TABLE IF NOT EXISTS politics.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES politics.storylines(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_politics_sei_entity_name ON politics.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_politics_sei_storyline ON politics.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_politics_sei_core ON politics.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_politics_sei_entity_type ON politics.story_entity_index (entity_type);

-- finance
CREATE TABLE IF NOT EXISTS finance.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES finance.storylines(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_finance_sei_entity_name ON finance.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_finance_sei_storyline ON finance.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_finance_sei_core ON finance.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_finance_sei_entity_type ON finance.story_entity_index (entity_type);

-- science_tech
CREATE TABLE IF NOT EXISTS science_tech.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES science_tech.storylines(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_science_tech_sei_entity_name ON science_tech.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_science_tech_sei_storyline ON science_tech.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_science_tech_sei_core ON science_tech.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_science_tech_sei_entity_type ON science_tech.story_entity_index (entity_type);

COMMENT ON TABLE politics.story_entity_index IS 'v5: entity mentions per storyline for event→storyline matching (story_continuation)';
COMMENT ON TABLE finance.story_entity_index IS 'v5: entity mentions per storyline for event→storyline matching (story_continuation)';
COMMENT ON TABLE science_tech.story_entity_index IS 'v5: entity mentions per storyline for event→storyline matching (story_continuation)';
