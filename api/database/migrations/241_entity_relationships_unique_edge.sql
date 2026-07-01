-- Unique edge identity for intelligence.entity_relationships (co_mention dedupe).
-- Run dedupe_entity_relationships.py BEFORE applying in production if duplicates exist.
-- CONCURRENTLY cannot run inside a transaction; migration runner may apply non-concurrent fallback.

CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_edge
ON intelligence.entity_relationships (
    source_domain,
    source_entity_id,
    target_domain,
    target_entity_id,
    relationship_type
);
