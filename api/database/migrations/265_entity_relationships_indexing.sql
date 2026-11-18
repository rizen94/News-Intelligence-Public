-- Migration 265: Targeted indexing for entity_relationships table
-- Addresses frontend timeouts by optimizing common query patterns

BEGIN;

-- Add composite indexes for common query patterns
-- Index for querying relationships by source domain and entity ID (existing index already exists)
-- CREATE INDEX IF NOT EXISTS idx_intelligence_entity_rel_source ON intelligence.entity_relationships(source_domain, source_entity_id);
-- This index already exists from migration 141

-- Index for querying relationships by target domain and entity ID (existing index already exists)
-- CREATE INDEX IF NOT EXISTS idx_intelligence_entity_rel_target ON intelligence.entity_relationships(target_domain, target_entity_id);
-- This index already exists from migration 141

-- Add composite index for relationship type and timestamp filtering
-- This is critical for network graph queries that filter by relationship type and time range
CREATE INDEX IF NOT EXISTS idx_intelligence_entity_rel_type_timestamp ON intelligence.entity_relationships(relationship_type, created_at DESC);

-- Add composite index for entity type and timestamp filtering  
-- This supports queries that filter by entity types (source or target) with time constraints
CREATE INDEX IF NOT EXISTS idx_intelligence_entity_rel_source_type_timestamp ON intelligence.entity_relationships(source_domain, source_entity_id, created_at DESC);

-- Add composite index for reverse entity relationship queries
CREATE INDEX IF NOT EXISTS idx_intelligence_entity_rel_target_type_timestamp ON intelligence.entity_relationships(target_domain, target_entity_id, created_at DESC);

-- Add composite index for confidence and timestamp filtering
-- This supports queries that need to filter by confidence score with time constraints
CREATE INDEX IF NOT EXISTS idx_intelligence_entity_rel_confidence_timestamp ON intelligence.entity_relationships(confidence DESC, created_at DESC);

-- Add composite index for domain-qualified entity queries with timestamps
-- This supports network graph queries that need to find relationships for specific entities within time ranges
CREATE INDEX IF NOT EXISTS idx_intelligence_entity_rel_domain_entity_timestamp ON intelligence.entity_relationships(source_domain, target_domain, created_at DESC);

COMMIT;