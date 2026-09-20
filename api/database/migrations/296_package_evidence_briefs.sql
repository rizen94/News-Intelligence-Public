-- Migration 296: Package evidence briefs (Narrative evidence-expand + shared cited profile).
-- Package-bound educational event/research brief; Editor publishes news_stories from briefs.
-- Idempotent.

CREATE SCHEMA IF NOT EXISTS intelligence;

CREATE TABLE IF NOT EXISTS intelligence.package_evidence_briefs (
    id BIGSERIAL PRIMARY KEY,
    package_id BIGINT NOT NULL
        REFERENCES intelligence.editorial_packages(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'expanding', 'ready', 'stale')),
    lede TEXT,
    brief_md TEXT NOT NULL DEFAULT '',
    open_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    citation_registry JSONB NOT NULL DEFAULT '{}'::jsonb,
    gap_ledger JSONB NOT NULL DEFAULT '[]'::jsonb,
    vault_rel_path TEXT,
    expand_round INT NOT NULL DEFAULT 0,
    density JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    material_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (package_id)
);

CREATE INDEX IF NOT EXISTS idx_package_evidence_briefs_status
    ON intelligence.package_evidence_briefs (status, updated_at DESC);

COMMENT ON TABLE intelligence.package_evidence_briefs IS
  'v11: package-bound cited educational brief (Narrative evidence-expand + Research parity); Editor consumes for publish';

CREATE TABLE IF NOT EXISTS intelligence.package_evidence_brief_revisions (
    id BIGSERIAL PRIMARY KEY,
    brief_id BIGINT NOT NULL
        REFERENCES intelligence.package_evidence_briefs(id) ON DELETE CASCADE,
    lede TEXT,
    brief_md TEXT NOT NULL DEFAULT '',
    open_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    citation_registry JSONB NOT NULL DEFAULT '{}'::jsonb,
    gap_ledger JSONB NOT NULL DEFAULT '[]'::jsonb,
    expand_round INT,
    editor_actor TEXT,
    model_prompt_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_package_evidence_brief_revisions_brief
    ON intelligence.package_evidence_brief_revisions (brief_id, created_at DESC);

DO $$
BEGIN
  RAISE NOTICE 'Migration 296: package_evidence_briefs tables ensured';
END $$;
