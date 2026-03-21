-- Migration 145: Context–entity mentions (Phase 1.3)
-- Links contexts to entity_profiles for entity-centric views. Populated when context exists for an article
-- and article_entities (with canonical_entity_id) are mapped via old_entity_to_new to entity_profiles.
-- See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md

CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;

CREATE TABLE IF NOT EXISTS intelligence.context_entity_mentions (
    id SERIAL PRIMARY KEY,
    context_id INTEGER NOT NULL REFERENCES intelligence.contexts(id) ON DELETE CASCADE,
    entity_profile_id INTEGER NOT NULL REFERENCES intelligence.entity_profiles(id) ON DELETE CASCADE,
    confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
    source_snippet TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(context_id, entity_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_context_entity_mentions_context ON intelligence.context_entity_mentions(context_id);
CREATE INDEX IF NOT EXISTS idx_intelligence_context_entity_mentions_profile ON intelligence.context_entity_mentions(entity_profile_id);

COMMENT ON TABLE intelligence.context_entity_mentions IS 'Entity mentions per context; links contexts to entity_profiles for entity-centric search and profile building';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.context_entity_mentions TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.context_entity_mentions_id_seq TO newsapp;
