-- Migration 297: allow closed_thin package status (v12 publish escape)
-- Forward-only; additive status value for max-rounds / stakes thin close.

DO $$
DECLARE
    conname text;
BEGIN
    SELECT c.conname INTO conname
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    JOIN pg_namespace n ON t.relnamespace = n.oid
    WHERE n.nspname = 'intelligence'
      AND t.relname = 'editorial_packages'
      AND c.contype = 'c'
      AND pg_get_constraintdef(c.oid) ILIKE '%status%';

    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE intelligence.editorial_packages DROP CONSTRAINT %I', conname);
    END IF;
END $$;

ALTER TABLE intelligence.editorial_packages
    ADD CONSTRAINT editorial_packages_status_check
    CHECK (status IN (
        'draft', 'in_research', 'in_narrative', 'in_reduction',
        'ready_for_editor', 'in_editing', 'published', 'blocked', 'archived',
        'closed_thin'
    ));

COMMENT ON CONSTRAINT editorial_packages_status_check ON intelligence.editorial_packages IS
    'v12: closed_thin for max-rounds / deterministic stakes escape (not ready_for_editor).';
