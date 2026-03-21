-- Migration 151: Phase 1 RAG Enhancement — versioned facts for entity profiles
-- See docs/RAG_ENHANCEMENT_ROADMAP.md and docs/VECTOR_DATABASE_SCHEMA.md.
-- Facts are tied to entity_profiles; optional embedding column can be added later for vector search.

CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;

-- Versioned facts per entity profile (POSITION, STATEMENT, ACTION, RELATIONSHIP)
CREATE TABLE IF NOT EXISTS intelligence.versioned_facts (
    id SERIAL PRIMARY KEY,
    entity_profile_id INTEGER NOT NULL REFERENCES intelligence.entity_profiles(id) ON DELETE CASCADE,
    fact_type VARCHAR(50) NOT NULL CHECK (fact_type IN (
        'POSITION', 'STATEMENT', 'ACTION', 'RELATIONSHIP', 'ATTRIBUTE'
    )),
    fact_text TEXT NOT NULL,
    valid_from TIMESTAMP WITH TIME ZONE,
    valid_to TIMESTAMP WITH TIME ZONE,
    confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
    sources JSONB DEFAULT '[]',
    superseded_by_id INTEGER REFERENCES intelligence.versioned_facts(id) ON DELETE SET NULL,
    extraction_method VARCHAR(50) DEFAULT 'llm_extraction',
    verification_status VARCHAR(30) DEFAULT 'unverified',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_versioned_facts_entity_profile ON intelligence.versioned_facts(entity_profile_id);
CREATE INDEX IF NOT EXISTS idx_versioned_facts_type ON intelligence.versioned_facts(fact_type);
CREATE INDEX IF NOT EXISTS idx_versioned_facts_valid ON intelligence.versioned_facts(valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_versioned_facts_superseded ON intelligence.versioned_facts(superseded_by_id) WHERE superseded_by_id IS NOT NULL;

COMMENT ON TABLE intelligence.versioned_facts IS 'Versioned facts per entity profile; supports temporal queries and supersession chain';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.versioned_facts TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.versioned_facts_id_seq TO newsapp;
