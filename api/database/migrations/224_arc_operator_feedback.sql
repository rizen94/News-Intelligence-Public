-- Migration 224: Operator workflow — arc report feedback (Phase 6)
-- See docs/LONGITUDINAL_OPERATOR_RUNBOOK.md

BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.arc_report_feedback (
    id bigserial PRIMARY KEY,
    arc_id text NOT NULL REFERENCES intelligence.arc_definitions(arc_id),
    report_id bigint REFERENCES intelligence.arc_reports(id) ON DELETE SET NULL,
    section_key text NOT NULL DEFAULT 'overall',
    rating integer CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    useful boolean,
    notes text,
    curator text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_arc_report_feedback_arc
    ON intelligence.arc_report_feedback (arc_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_arc_report_feedback_report
    ON intelligence.arc_report_feedback (report_id);

CREATE TABLE IF NOT EXISTS intelligence.reference_event_flags (
    id bigserial PRIMARY KEY,
    reference_event_id bigint REFERENCES intelligence.reference_events(id) ON DELETE CASCADE,
    flag_type text NOT NULL DEFAULT 'missed_coverage'
        CHECK (flag_type IN ('missed_coverage', 'needs_correction', 'high_value')),
    notes text,
    curator text,
    created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reference_event_flags_event
    ON intelligence.reference_event_flags (reference_event_id);

COMMIT;
