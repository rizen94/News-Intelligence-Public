-- Migration 143: Context-centric entity profiles, entity mapping, claims, pattern_discoveries (Phase 1.1)
-- See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md. intelligence.entity_relationships already exists (141).

CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;

-- Living documents per canonical entity (align with v6 entity_dossiers concept)
-- canonical_entity_id = entity_canonical.id in schema for domain_key (no cross-schema FK)
CREATE TABLE IF NOT EXISTS intelligence.entity_profiles (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    canonical_entity_id INTEGER NOT NULL,
    compilation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    sections JSONB DEFAULT '[]',       -- Wikipedia-style sections
    relationships_summary JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain_key, canonical_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_entity_profiles_domain ON intelligence.entity_profiles(domain_key);
CREATE INDEX IF NOT EXISTS idx_intelligence_entity_profiles_updated ON intelligence.entity_profiles(updated_at DESC);

COMMENT ON TABLE intelligence.entity_profiles IS 'Living documents per canonical entity; extends entity_canonical with compiled sections and relationships';

-- Maps current entity identifiers to entity_profiles (preserve lineage)
-- old_entity_id = entity_canonical.id in that domain; entity_profile_id = intelligence.entity_profiles.id
CREATE TABLE IF NOT EXISTS intelligence.old_entity_to_new (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    old_entity_id INTEGER NOT NULL,
    entity_profile_id INTEGER NOT NULL REFERENCES intelligence.entity_profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain_key, old_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_old_entity_to_new_lookup ON intelligence.old_entity_to_new(domain_key, old_entity_id);
CREATE INDEX IF NOT EXISTS idx_intelligence_old_entity_to_new_profile ON intelligence.old_entity_to_new(entity_profile_id);

COMMENT ON TABLE intelligence.old_entity_to_new IS 'Maps domain entity_canonical.id to entity_profiles.id for migration and lineage';

-- Atomic facts extracted from contexts (Phase 2 prep; table in place for pipeline)
CREATE TABLE IF NOT EXISTS intelligence.extracted_claims (
    id SERIAL PRIMARY KEY,
    context_id INTEGER NOT NULL REFERENCES intelligence.contexts(id) ON DELETE CASCADE,
    subject_text TEXT,
    predicate_text TEXT,
    object_text TEXT,
    confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
    valid_from TIMESTAMP WITH TIME ZONE,
    valid_to TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_extracted_claims_context ON intelligence.extracted_claims(context_id);
CREATE INDEX IF NOT EXISTS idx_intelligence_extracted_claims_subject ON intelligence.extracted_claims USING gin(to_tsvector('english', COALESCE(subject_text, '')));

COMMENT ON TABLE intelligence.extracted_claims IS 'Atomic facts (subject/predicate/object) from contexts; temporal and confidence';

-- Detected patterns (behavioral, temporal, network, event) — distinct from intelligence.patterns for richer structure
CREATE TABLE IF NOT EXISTS intelligence.pattern_discoveries (
    id SERIAL PRIMARY KEY,
    pattern_type VARCHAR(50) NOT NULL,   -- behavioral, temporal, network, event
    domain_key VARCHAR(50),
    context_ids INTEGER[],
    entity_profile_ids INTEGER[],
    confidence DECIMAL(3,2),
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_pattern_discoveries_type ON intelligence.pattern_discoveries(pattern_type);
CREATE INDEX IF NOT EXISTS idx_intelligence_pattern_discoveries_domain ON intelligence.pattern_discoveries(domain_key);

COMMENT ON TABLE intelligence.pattern_discoveries IS 'Detected patterns (behavioral, temporal, network, event) from context-centric analysis';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.entity_profiles TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.old_entity_to_new TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.extracted_claims TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.pattern_discoveries TO newsapp;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intelligence TO newsapp;
