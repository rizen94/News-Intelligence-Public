-- Migration 304: durable investigation dossier generation jobs (async POST for large containers)

CREATE TABLE IF NOT EXISTS intelligence.investigation_report_jobs (
    event_id INTEGER PRIMARY KEY
        REFERENCES intelligence.tracked_events (id) ON DELETE CASCADE,
    status TEXT NOT NULL
        CHECK (status IN ('queued', 'running', 'ready', 'failed')),
    error TEXT,
    contexts_total INTEGER,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_investigation_report_jobs_status_updated
    ON intelligence.investigation_report_jobs (status, updated_at DESC);

COMMENT ON TABLE intelligence.investigation_report_jobs IS
    'Operator-triggered investigation dossier jobs; large containers enqueue here and poll GET /tracked_events/{id}/report';

DO $$
BEGIN
    RAISE NOTICE 'Migration 304: investigation_report_jobs';
END $$;
