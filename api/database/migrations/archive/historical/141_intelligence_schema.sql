-- Migration 141: Intelligence schema for Newsroom Orchestrator v6
-- Patterns, entity relationships (domain-qualified), narrative threads, cross-domain links.
-- storyline_id in narrative_threads is in domain_key's storylines table.
-- cross_domain_links.links is JSONB array of {domain, article_id}.

CREATE SCHEMA IF NOT EXISTS intelligence;

GRANT USAGE ON SCHEMA intelligence TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA intelligence GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO newsapp;

-- Patterns (detected patterns per domain)
CREATE TABLE intelligence.patterns (
    id SERIAL PRIMARY KEY,
    pattern_type VARCHAR(50) NOT NULL,
    domain_key VARCHAR(50),
    confidence DECIMAL(3,2),
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intelligence_patterns_domain ON intelligence.patterns(domain_key);
CREATE INDEX idx_intelligence_patterns_type ON intelligence.patterns(pattern_type);

-- Entity relationships: domain-qualified (source/target domain + entity id per domain)
CREATE TABLE intelligence.entity_relationships (
    id SERIAL PRIMARY KEY,
    source_domain VARCHAR(50) NOT NULL,
    source_entity_id INTEGER NOT NULL,
    target_domain VARCHAR(50) NOT NULL,
    target_entity_id INTEGER NOT NULL,
    relationship_type VARCHAR(50),
    confidence DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intelligence_entity_rel_source ON intelligence.entity_relationships(source_domain, source_entity_id);
CREATE INDEX idx_intelligence_entity_rel_target ON intelligence.entity_relationships(target_domain, target_entity_id);

-- Narrative threads: domain_key + storyline_id refer to that domain's storylines
CREATE TABLE intelligence.narrative_threads (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    storyline_id INTEGER NOT NULL,
    summary TEXT,
    linked_article_ids INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intelligence_narrative_domain_storyline ON intelligence.narrative_threads(domain_key, storyline_id);

-- Cross-domain links: links JSONB = [{domain, article_id}, ...]
CREATE TABLE intelligence.cross_domain_links (
    id SERIAL PRIMARY KEY,
    source_domain VARCHAR(50) NOT NULL,
    target_domain VARCHAR(50) NOT NULL,
    entity_name VARCHAR(255),
    link_type VARCHAR(50),
    links JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intelligence_cross_domain_domains ON intelligence.cross_domain_links(source_domain, target_domain);

-- Investigation notes (references orchestration.investigations)
CREATE TABLE intelligence.investigation_notes (
    id SERIAL PRIMARY KEY,
    investigation_id INTEGER NOT NULL,
    note_type VARCHAR(50),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intelligence_investigation_notes_inv ON intelligence.investigation_notes(investigation_id);

-- FK to orchestration.investigations (same DB)
ALTER TABLE intelligence.investigation_notes
ADD CONSTRAINT fk_investigation_notes_investigation
FOREIGN KEY (investigation_id) REFERENCES orchestration.investigations(id) ON DELETE CASCADE;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA intelligence TO newsapp;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intelligence TO newsapp;

COMMENT ON TABLE intelligence.narrative_threads IS 'storyline_id is in schema for domain_key (e.g. politics.storylines)';
COMMENT ON TABLE intelligence.cross_domain_links IS 'links: JSONB array of {"domain": "politics", "article_id": 1}';
COMMENT ON TABLE intelligence.entity_relationships IS 'Entity IDs refer to entity_canonical in respective domain schema';
