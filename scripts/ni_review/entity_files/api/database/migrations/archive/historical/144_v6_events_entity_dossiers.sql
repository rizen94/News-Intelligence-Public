-- Migration 144: v6 event tracking and entity dossiers (V6_QUALITY_FIRST_UPGRADE_PLAN)
-- Run in parallel with context-centric work. See docs/V6_QUALITY_FIRST_UPGRADE_PLAN.md

CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;

-- Event tracking (election, legislation, investigation, market_event, etc.)
CREATE TABLE IF NOT EXISTS intelligence.tracked_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    event_name VARCHAR(300) NOT NULL,
    start_date DATE,
    end_date DATE,
    geographic_scope VARCHAR(100),
    key_participant_entity_ids JSONB DEFAULT '[]',
    milestones JSONB DEFAULT '[]',
    sub_event_ids INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_tracked_events_type ON intelligence.tracked_events(event_type);
CREATE INDEX IF NOT EXISTS idx_intelligence_tracked_events_dates ON intelligence.tracked_events(start_date, end_date);

-- Event chronicles (developments, analysis, momentum per event)
CREATE TABLE IF NOT EXISTS intelligence.event_chronicles (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES intelligence.tracked_events(id) ON DELETE CASCADE,
    update_date DATE NOT NULL,
    developments JSONB DEFAULT '[]',
    analysis JSONB DEFAULT '{}',
    predictions JSONB DEFAULT '[]',
    momentum_score DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_event_chronicles_event ON intelligence.event_chronicles(event_id);

-- Entity dossiers (chronicle_data, relationships, positions per domain entity)
-- entity_id = entity_canonical.id in that domain
CREATE TABLE IF NOT EXISTS intelligence.entity_dossiers (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    compilation_date DATE NOT NULL,
    chronicle_data JSONB DEFAULT '[]',
    relationships JSONB DEFAULT '[]',
    positions JSONB DEFAULT '[]',
    patterns JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain_key, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_entity_dossiers_domain ON intelligence.entity_dossiers(domain_key);

-- Entity positions (voting records, policy positions, statements)
CREATE TABLE IF NOT EXISTS intelligence.entity_positions (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    topic VARCHAR(255),
    position TEXT,
    confidence DECIMAL(3,2),
    evidence_refs JSONB DEFAULT '[]',
    date_range TSTZRANGE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_entity_positions_entity ON intelligence.entity_positions(domain_key, entity_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.tracked_events TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.event_chronicles TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.entity_dossiers TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.entity_positions TO newsapp;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intelligence TO newsapp;
