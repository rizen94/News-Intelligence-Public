-- Pipeline monitoring alerts (pipeline_monitoring_service._log_alert_to_database)
CREATE TABLE IF NOT EXISTS pipeline_alerts (
    id BIGSERIAL PRIMARY KEY,
    alert_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    alert_level TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    process_name TEXT,
    severity_score DOUBLE PRECISION,
    metadata JSONB DEFAULT '{}'::jsonb,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_timestamp ON pipeline_alerts (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_resolved ON pipeline_alerts (resolved) WHERE NOT resolved;
