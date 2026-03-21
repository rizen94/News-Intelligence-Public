-- Migration 161: Automation run history (chronological, survives API restart)
-- Persist each automation phase run so monitoring "last 24h" is based on ingestion/completion time, not process uptime.

CREATE TABLE IF NOT EXISTS automation_run_history (
    id BIGSERIAL PRIMARY KEY,
    phase_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE NOT NULL,
    success BOOLEAN NOT NULL DEFAULT true,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_automation_run_history_phase_name ON automation_run_history(phase_name);
CREATE INDEX IF NOT EXISTS idx_automation_run_history_started_at ON automation_run_history(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_run_history_finished_at ON automation_run_history(finished_at DESC);

COMMENT ON TABLE automation_run_history IS 'Per-run log of automation phases; used for process run summary (last 24h) independent of API restart';
