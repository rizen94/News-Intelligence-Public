-- Migration 153: Phase 2 RAG — storyline_states for tracking understanding over time
-- See docs/RAG_ENHANCEMENT_ROADMAP.md Phase 2. Storylines live in domain schemas; this table holds state snapshots keyed by (domain_key, storyline_id).

CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;

CREATE TABLE IF NOT EXISTS intelligence.storyline_states (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    storyline_id INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    state_summary TEXT,
    maturity_score DECIMAL(3,2) CHECK (maturity_score >= 0 AND maturity_score <= 1),
    key_entity_ids JSONB DEFAULT '[]',
    key_fact_ids JSONB DEFAULT '[]',
    knowledge_gaps JSONB DEFAULT '[]',
    significant_change BOOLEAN DEFAULT FALSE,
    change_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_storyline_states_domain_story ON intelligence.storyline_states(domain_key, storyline_id);
CREATE INDEX IF NOT EXISTS idx_storyline_states_created ON intelligence.storyline_states(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_storyline_states_maturity ON intelligence.storyline_states(maturity_score DESC NULLS LAST);

COMMENT ON TABLE intelligence.storyline_states IS 'Phase 2: state snapshots per storyline (domain_key, storyline_id); maturity_score 0-1, knowledge_gaps for enhancement queries';

GRANT SELECT, INSERT, UPDATE ON intelligence.storyline_states TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.storyline_states_id_seq TO newsapp;
