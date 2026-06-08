-- Migration 225: Longitudinal schema alignment after P0 trust fixes
-- - quarantine report_type for failed slow-report validation
-- - sanctions entity_qids GIN index for arc context queries
-- Note: cross_domain_correlations already exists (context-centric schema); do not recreate.

BEGIN;

-- arc_reports.report_type: add quarantine (validation-failed briefs)
ALTER TABLE intelligence.arc_reports
    DROP CONSTRAINT IF EXISTS arc_reports_report_type_check;

ALTER TABLE intelligence.arc_reports
    ADD CONSTRAINT arc_reports_report_type_check
    CHECK (report_type IN ('weekly_brief', 'material_change', 'manual', 'quarantine'));

COMMENT ON CONSTRAINT arc_reports_report_type_check ON intelligence.arc_reports IS
    'weekly_brief=published; quarantine=validation failed (excluded from latest API)';

-- Sanctions overlap with arc primary_entity_qids
CREATE INDEX IF NOT EXISTS idx_sanctions_actions_entity_qids
    ON intelligence.sanctions_actions USING gin (entity_qids);

-- Arc-scoped correlation lookup (existing table from context-centric pipeline)
CREATE INDEX IF NOT EXISTS idx_cross_domain_correlations_metadata_arc
    ON intelligence.cross_domain_correlations ((metadata->>'arc_id'))
    WHERE metadata->>'arc_id' IS NOT NULL;

COMMIT;
