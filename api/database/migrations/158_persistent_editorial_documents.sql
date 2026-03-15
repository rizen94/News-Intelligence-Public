-- Migration 158: Persistent editorial documents (write once, refine forever)
-- See docs/PERSISTENT_EDITORIAL_DOCUMENTS.md
-- Adds: storyline editorial_document columns (per domain), investigation_dossiers, tracked_events briefing columns, document_refinements log.

-- =============================================================================
-- 1. Per-domain storylines: editorial document and versioning
-- =============================================================================
DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT domains.schema_name FROM public.domains WHERE is_active = true
    LOOP
        EXECUTE format('ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS editorial_document JSONB DEFAULT %L', schema_name, '{}');
        EXECUTE format('ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS document_version INTEGER DEFAULT 0', schema_name);
        EXECUTE format('ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS document_status TEXT DEFAULT %L', schema_name, 'draft');
        EXECUTE format('ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS last_refinement TIMESTAMPTZ', schema_name);
        EXECUTE format('ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS refinement_triggers JSONB DEFAULT %L', schema_name, '[]');
        RAISE NOTICE 'Added editorial columns to %.storylines', schema_name;
    END LOOP;
END $$;

-- =============================================================================
-- 2. Intelligence: investigation dossiers (references orchestration.investigations from migration 140)
-- =============================================================================
CREATE TABLE IF NOT EXISTS intelligence.investigation_dossiers (
    investigation_id INTEGER PRIMARY KEY,
    dossier_document JSONB NOT NULL DEFAULT '{}'::jsonb,
    document_version INTEGER DEFAULT 0,
    sections_updated JSONB DEFAULT '{}'::jsonb,
    quality_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_refined TIMESTAMPTZ
);
COMMENT ON TABLE intelligence.investigation_dossiers IS 'Persistent editorial dossiers for investigations; document_type investigation.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'orchestration' AND table_name = 'investigations') THEN
        ALTER TABLE intelligence.investigation_dossiers
            DROP CONSTRAINT IF EXISTS investigation_dossiers_investigation_id_fkey;
        ALTER TABLE intelligence.investigation_dossiers
            ADD CONSTRAINT investigation_dossiers_investigation_id_fkey
            FOREIGN KEY (investigation_id) REFERENCES orchestration.investigations(id) ON DELETE CASCADE;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'FK to orchestration.investigations skipped: %', SQLERRM;
END $$;

-- =============================================================================
-- 3. Tracked events: editorial briefing columns
-- =============================================================================
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS editorial_briefing TEXT;
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS editorial_briefing_json JSONB DEFAULT '{}'::jsonb;
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS briefing_version INTEGER DEFAULT 0;
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS briefing_status TEXT DEFAULT 'draft';
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS last_briefing_update TIMESTAMPTZ;

-- =============================================================================
-- 4. Document refinement log
-- =============================================================================
CREATE TABLE IF NOT EXISTS intelligence.document_refinements (
    refinement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type TEXT NOT NULL,
    domain_key TEXT,
    document_id TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    sections_updated TEXT[],
    refinement_prompt_snippet TEXT,
    before_version INTEGER,
    after_version INTEGER,
    quality_delta FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_document_refinements_doc ON intelligence.document_refinements(document_type, document_id);
CREATE INDEX IF NOT EXISTS idx_document_refinements_created ON intelligence.document_refinements(created_at DESC);
COMMENT ON TABLE intelligence.document_refinements IS 'Log of editorial document refinements for learning and audit.';
