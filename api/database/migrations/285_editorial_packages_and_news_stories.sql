-- Migration 285: Editorial packages, modal handoffs, news stories (v11).
-- Local news_intel_dev first; do NOT apply on Widow until v11 cutover.
-- Idempotent.

CREATE SCHEMA IF NOT EXISTS intelligence;

-- ---------------------------------------------------------------------------
-- Editorial packages (the artifact passed between modals)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intelligence.editorial_packages (
    id BIGSERIAL PRIMARY KEY,
    working_title TEXT NOT NULL DEFAULT '',
    summary_stub TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft', 'in_research', 'in_narrative', 'in_reduction',
            'ready_for_editor', 'in_editing', 'published', 'blocked', 'archived'
        )),
    presentation_kind TEXT NOT NULL DEFAULT 'unset'
        CHECK (presentation_kind IN (
            'unset', 'research_brief', 'event_narrative', 'hybrid'
        )),
    domain_keys TEXT[] NOT NULL DEFAULT '{}',
    primary_modal TEXT
        CHECK (primary_modal IS NULL OR primary_modal IN (
            'intake', 'research', 'narrative', 'reduction', 'editor'
        )),
    readiness JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_editorial_packages_status
    ON intelligence.editorial_packages (status);
CREATE INDEX IF NOT EXISTS idx_editorial_packages_domain_keys
    ON intelligence.editorial_packages USING GIN (domain_keys);
CREATE INDEX IF NOT EXISTS idx_editorial_packages_updated
    ON intelligence.editorial_packages (updated_at DESC);

COMMENT ON TABLE intelligence.editorial_packages IS
  'v11: typed package of research + narrative members passed between modals; Editor publishes news_stories from packages';

CREATE TABLE IF NOT EXISTS intelligence.editorial_package_members (
    id BIGSERIAL PRIMARY KEY,
    package_id BIGINT NOT NULL
        REFERENCES intelligence.editorial_packages(id) ON DELETE CASCADE,
    member_family TEXT NOT NULL
        CHECK (member_family IN ('research', 'narrative')),
    member_type TEXT NOT NULL
        CHECK (member_type IN (
            'extracted_claim', 'versioned_fact', 'claim_evidence_appraisal',
            'hypothesis', 'processed_document', 'article', 'context',
            'chronological_event', 'entity', 'location', 'time_span',
            'movement_edge', 'graph_link'
        )),
    member_id BIGINT NOT NULL,
    domain_key TEXT,
    role TEXT NOT NULL DEFAULT 'supporting',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'quarantined', 'removed')),
    added_by_modal TEXT
        CHECK (added_by_modal IS NULL OR added_by_modal IN (
            'intake', 'research', 'narrative', 'reduction', 'editor'
        )),
    added_by TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (package_id, member_family, member_type, member_id)
);

CREATE INDEX IF NOT EXISTS idx_ep_members_package
    ON intelligence.editorial_package_members (package_id, status);
CREATE INDEX IF NOT EXISTS idx_ep_members_type
    ON intelligence.editorial_package_members (member_type, member_id);

CREATE TABLE IF NOT EXISTS intelligence.editorial_package_links (
    id BIGSERIAL PRIMARY KEY,
    package_id BIGINT NOT NULL
        REFERENCES intelligence.editorial_packages(id) ON DELETE CASCADE,
    from_member_id BIGINT NOT NULL
        REFERENCES intelligence.editorial_package_members(id) ON DELETE CASCADE,
    to_member_id BIGINT NOT NULL
        REFERENCES intelligence.editorial_package_members(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL
        CHECK (link_type IN (
            'supports', 'contradicts', 'same_event', 'near_in_time', 'same_place',
            'movement', 'caused_by', 'corroborates', 'derived_from'
        )),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    inference_stage TEXT NOT NULL DEFAULT 'hypothesized'
        CHECK (inference_stage IN (
            'hypothesized', 'candidate', 'established', 'quarantined'
        )),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'removed')),
    domain_keys TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (from_member_id <> to_member_id)
);

CREATE INDEX IF NOT EXISTS idx_ep_links_package
    ON intelligence.editorial_package_links (package_id, status);

CREATE TABLE IF NOT EXISTS intelligence.editorial_package_decisions (
    id BIGSERIAL PRIMARY KEY,
    package_id BIGINT NOT NULL
        REFERENCES intelligence.editorial_packages(id) ON DELETE CASCADE,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor TEXT NOT NULL DEFAULT 'operator',
    modal TEXT
        CHECK (modal IS NULL OR modal IN (
            'intake', 'research', 'narrative', 'reduction', 'editor'
        )),
    action TEXT NOT NULL
        CHECK (action IN (
            'member_added', 'member_removed', 'member_quarantined',
            'link_added', 'link_removed', 'kind_set', 'ready_for_editor',
            'cleared', 'blocked', 'rework_requested', 'prose_drafted',
            'prose_published', 'citation_bound', 'citation_refused',
            'status_changed', 'package_created'
        )),
    member_id BIGINT,
    link_id BIGINT,
    rationale TEXT,
    source_refs JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_prompt_version TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ep_decisions_package
    ON intelligence.editorial_package_decisions (package_id, at DESC);

-- ---------------------------------------------------------------------------
-- Modal handoffs (package-centric)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intelligence.modal_handoffs (
    id BIGSERIAL PRIMARY KEY,
    package_id BIGINT
        REFERENCES intelligence.editorial_packages(id) ON DELETE SET NULL,
    source_modal TEXT NOT NULL
        CHECK (source_modal IN (
            'intake', 'research', 'narrative', 'reduction', 'editor', 'system'
        )),
    target_modal TEXT NOT NULL
        CHECK (target_modal IN (
            'intake', 'research', 'narrative', 'reduction', 'editor'
        )),
    object_type TEXT NOT NULL DEFAULT 'editorial_package',
    object_id BIGINT,
    focus_member_id BIGINT,
    domain_keys TEXT[] NOT NULL DEFAULT '{}',
    reason_code TEXT NOT NULL DEFAULT 'manual',
    note TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'accepted', 'done', 'dismissed')),
    created_by TEXT NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_modal_handoffs_target_open
    ON intelligence.modal_handoffs (target_modal, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_modal_handoffs_package
    ON intelligence.modal_handoffs (package_id);

-- ---------------------------------------------------------------------------
-- News stories (final longform product)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intelligence.news_stories (
    id BIGSERIAL PRIMARY KEY,
    package_id BIGINT NOT NULL
        REFERENCES intelligence.editorial_packages(id) ON DELETE RESTRICT,
    title TEXT NOT NULL DEFAULT '',
    lede TEXT,
    body_md TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'in_review', 'published', 'recalled')),
    presentation_kind TEXT NOT NULL DEFAULT 'unset'
        CHECK (presentation_kind IN (
            'unset', 'research_brief', 'event_narrative', 'hybrid'
        )),
    domain_keys TEXT[] NOT NULL DEFAULT '{}',
    published_at TIMESTAMPTZ,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_news_stories_package
    ON intelligence.news_stories (package_id);
CREATE INDEX IF NOT EXISTS idx_news_stories_status
    ON intelligence.news_stories (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS intelligence.news_story_revisions (
    id BIGSERIAL PRIMARY KEY,
    story_id BIGINT NOT NULL
        REFERENCES intelligence.news_stories(id) ON DELETE CASCADE,
    title TEXT,
    lede TEXT,
    body_md TEXT NOT NULL DEFAULT '',
    editor_actor TEXT,
    model_prompt_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_news_story_revisions_story
    ON intelligence.news_story_revisions (story_id, created_at DESC);

CREATE TABLE IF NOT EXISTS intelligence.news_story_citations (
    id BIGSERIAL PRIMARY KEY,
    story_id BIGINT NOT NULL
        REFERENCES intelligence.news_stories(id) ON DELETE CASCADE,
    package_member_id BIGINT
        REFERENCES intelligence.editorial_package_members(id) ON DELETE SET NULL,
    span_start INT,
    span_end INT,
    citation_marker TEXT,
    source_table TEXT,
    source_row_id BIGINT,
    source_url TEXT,
    quote TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_news_story_citations_story
    ON intelligence.news_story_citations (story_id);

DO $$
BEGIN
  RAISE NOTICE 'Migration 285: editorial packages, modal handoffs, news stories ensured';
END $$;
