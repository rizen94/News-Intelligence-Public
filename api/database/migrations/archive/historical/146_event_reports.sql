-- Migration 146: Store generated investigation reports (dossier) per tracked event.
-- Enables "last report" display and regeneration when context set changes.

CREATE TABLE IF NOT EXISTS intelligence.event_reports (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES intelligence.tracked_events(id) ON DELETE CASCADE,
    report_md TEXT NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    context_ids_included INTEGER[] DEFAULT '{}',
    chronicle_count INTEGER DEFAULT 0,
    context_count INTEGER DEFAULT 0,
    UNIQUE(event_id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_event_reports_event ON intelligence.event_reports(event_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.event_reports TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.event_reports_id_seq TO newsapp;

COMMENT ON TABLE intelligence.event_reports IS 'Latest journalism-style dossier per tracked event; replace on regenerate.';
