-- Migration 257: Entity profile provenance + cross-domain timeline enhancements
-- Part of pipeline audit follow-up (Nov 2026):
--   1. Add seed-context provenance to entity_profiles for traceability back to articles.
--   2. Track first-extraction timestamp for each profile.
--   3. Flag cross-domain entities that get priority despite low absolute mention count.
--   4. Add source_context_ids to cross_domain_correlations linking back to seed contexts.
--   5. Allow temporal/thematic correlation types (stored in metadata.type when type=entity_overlap).

BEGIN;

-- =========================================================================
-- Step 1: Entity profile provenance columns
-- =========================================================================

ALTER TABLE intelligence.entity_profiles
    ADD COLUMN IF NOT EXISTS seed_context_ids INTEGER[] DEFAULT '{}';

COMMENT ON COLUMN intelligence.entity_profiles.seed_context_ids IS
    'Context IDs that seeded this entity profile — links back to article extracts and extraction events for provenance tracing';

ALTER TABLE intelligence.entity_profiles
    ADD COLUMN IF NOT EXISTS first_extraction_at TIMESTAMPTZ;

COMMENT ON COLUMN intelligence.entity_profiles.first_extraction_at IS
    'Timestamp of the earliest context/claim that contributed to this entity profile';

ALTER TABLE intelligence.entity_profiles
    ADD COLUMN IF NOT EXISTS multi_domain_priority BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN intelligence.entity_profiles.multi_domain_priority IS
    'True when entity appears in >=2 domains — granted profile priority regardless of absolute mention count';

CREATE INDEX IF NOT EXISTS idx_entity_profiles_seed_context ON intelligence.entity_profiles USING GIN(seed_context_ids);
CREATE INDEX IF NOT EXISTS idx_entity_profiles_multi_domain ON intelligence.entity_profiles(multi_domain_priority) WHERE multi_domain_priority = TRUE;

-- =========================================================================
-- Step 2: Cross-domain correlation provenance + metadata enrichment
-- =========================================================================

ALTER TABLE intelligence.cross_domain_correlations
    ADD COLUMN IF NOT EXISTS source_context_ids INTEGER[] DEFAULT '{}';

COMMENT ON COLUMN intelligence.cross_domain_correlations.source_context_ids IS
    'Seed context IDs that triggered this cross-domain correlation — links back to article_entities for full lineage tracing';

CREATE INDEX IF NOT EXISTS idx_cross_domain_correlations_source_context ON intelligence.cross_domain_correlations USING GIN(source_context_ids);

-- =========================================================================
-- Step 3: Backfill first_extraction_at from context_entity_mentions + contexts
-- =========================================================================

UPDATE intelligence.entity_profiles ep
SET first_extraction_at = sub.first_ctx_created
FROM (
    SELECT cem.entity_profile_id, MIN(c.created_at) AS first_ctx_created
    FROM intelligence.context_entity_mentions cem
    JOIN intelligence.contexts c ON c.id = cem.context_id
    GROUP BY cem.entity_profile_id
) sub
WHERE ep.id = sub.entity_profile_id
  AND ep.first_extraction_at IS NULL;

-- =========================================================================
-- Step 4: Flag cross-domain entities for priority
-- =========================================================================

UPDATE intelligence.entity_profiles ep
SET multi_domain_priority = TRUE
FROM (
    SELECT entity_profile_id, COUNT(DISTINCT domain_key) AS domain_count
    FROM (
        SELECT DISTINCT cem.entity_profile_id, c.domain_key
        FROM intelligence.context_entity_mentions cem
        JOIN intelligence.contexts c ON c.id = cem.context_id
    ) cross_doms
    GROUP BY entity_profile_id
    HAVING COUNT(DISTINCT domain_key) >= 2
) flagged
WHERE ep.id = flagged.entity_profile_id
  AND ep.multi_domain_priority = FALSE;

-- =========================================================================
-- Step 5: Verify results
-- =========================================================================

DO $$
DECLARE
    v_profiles_count       bigint;
    v_provenance_filled   bigint;
    v_multi_domain        bigint;
    v_correlations_count  bigint;
BEGIN
    SELECT count(*) INTO v_profiles_count FROM intelligence.entity_profiles;
    SELECT count(*) INTO v_provenance_filled FROM intelligence.entity_profiles WHERE seed_context_ids IS NOT NULL AND array_length(seed_context_ids, 1) > 0;
    SELECT count(*) INTO v_multi_domain FROM intelligence.entity_profiles WHERE multi_domain_priority = TRUE;
    SELECT count(*) INTO v_correlations_count FROM intelligence.cross_domain_correlations;
    RAISE NOTICE 'Migration 257 complete: profiles=%, provenance-filled=%, multi-domain-flags=%, correlations=%',
        v_profiles_count, v_provenance_filled, v_multi_domain, v_correlations_count;
END $$;

COMMIT;
