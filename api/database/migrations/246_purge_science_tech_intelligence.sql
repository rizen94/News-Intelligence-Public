-- Migration 246: Purge retired science-tech rows from intelligence (schema dropped in 212).
-- Removes orphan entity_profiles, facts, contexts, and related queue rows that poison
-- dossier/profile catch-up selectors.

BEGIN;

CREATE TEMP TABLE _purge_science_profile_ids ON COMMIT DROP AS
SELECT id
FROM intelligence.entity_profiles
WHERE domain_key IN ('science-tech', 'science_tech');

CREATE TEMP TABLE _purge_science_context_ids ON COMMIT DROP AS
SELECT id
FROM intelligence.contexts
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.fact_change_log
WHERE entity_profile_id IN (SELECT id FROM _purge_science_profile_ids);

DELETE FROM intelligence.versioned_facts
WHERE entity_profile_id IN (SELECT id FROM _purge_science_profile_ids);

DELETE FROM intelligence.context_entity_mentions
WHERE entity_profile_id IN (SELECT id FROM _purge_science_profile_ids)
   OR context_id IN (SELECT id FROM _purge_science_context_ids);

DELETE FROM intelligence.article_to_context
WHERE context_id IN (SELECT id FROM _purge_science_context_ids);

DELETE FROM intelligence.contexts
WHERE id IN (SELECT id FROM _purge_science_context_ids);

DELETE FROM intelligence.entity_dossiers
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.entity_positions
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.entity_relationships
WHERE source_domain IN ('science-tech', 'science_tech')
   OR target_domain IN ('science-tech', 'science_tech');

DELETE FROM intelligence.cross_domain_links
WHERE source_domain IN ('science-tech', 'science_tech')
   OR target_domain IN ('science-tech', 'science_tech');

DELETE FROM intelligence.old_entity_to_new
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.story_update_queue
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.storyline_states
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.embedding_chunks
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.pattern_discoveries
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.pattern_matches
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.patterns
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.content_refinement_queue
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.narrative_threads
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.document_refinements
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.storyline_rag_context
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.watch_patterns
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.saved_intel_outputs
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.claim_subject_gap_catalog
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.article_duplicate_sources
WHERE domain_key IN ('science-tech', 'science_tech');

DELETE FROM intelligence.entity_profiles
WHERE domain_key IN ('science-tech', 'science_tech');

UPDATE intelligence.tracked_events
SET domain_keys = array_remove(array_remove(domain_keys, 'science-tech'), 'science_tech')
WHERE domain_keys && ARRAY['science-tech', 'science_tech']::text[];

COMMIT;
