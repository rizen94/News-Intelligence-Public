-- Migration: create_knowledge_subject_summary
--
-- Purpose: Replace heavy per-request LEFT JOINs across knowledge_profiles +
-- is_assertions + is_not_assertions + open_questions + research_paper_profiles
-- with a single pre-computed row-per-entity from knowledge_subject_summary.
--
-- Update path: compiled by bridge service after each drain cycle
-- (research_literature_bridge_service.compile_subjects_for_ui).
-- The summary table is the authoritative fast-path for the Research Subjects UI.

CREATE TABLE IF NOT EXISTS intelligence.knowledge_subject_summary (
    domain_key                  VARCHAR(64) NOT NULL,
    canonical_entity_id         INT         NOT NULL,

    title                       VARCHAR(512),
    status                      VARCHAR(20),  -- 'published' | 'draft'

    -- Pre-aggregated counts used by ResearchPage cards
    is_assertion_count          INT     NOT NULL DEFAULT 0,
    is_not_assertion_count      INT     NOT NULL DEFAULT 0,
    open_question_count         INT     NOT NULL DEFAULT 0,
    total_papers                INT     NOT NULL DEFAULT 0,

    -- When the summary was last materialized (from knowledge_profiles)
    material_updated_at         TIMESTAMPTZ,

    PRIMARY KEY (domain_key, canonical_entity_id)
);
