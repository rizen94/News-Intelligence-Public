-- Migration 266: Rollback for entity_relationships indexing
-- Reverts the indexing changes made in migration 265

BEGIN;

-- Drop the composite indexes created in migration 265
-- Note: The existing source and target domain indexes (from migration 141) are kept as they're fundamental
DROP INDEX IF EXISTS idx_intelligence_entity_rel_type_timestamp;
DROP INDEX IF EXISTS idx_intelligence_entity_rel_source_type_timestamp;
DROP INDEX IF EXISTS idx_intelligence_entity_rel_target_type_timestamp;
DROP INDEX IF EXISTS idx_intelligence_entity_rel_confidence_timestamp;
DROP INDEX IF EXISTS idx_intelligence_entity_rel_domain_entity_timestamp;

COMMIT;