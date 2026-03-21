-- Migration 157: Anomaly investigations (record when anomalies are reviewed/dismissed)
-- See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md (section 10)

CREATE TABLE IF NOT EXISTS intelligence.anomaly_investigations (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    anomaly_type TEXT,
    action TEXT NOT NULL DEFAULT 'investigated',  -- 'investigated' | 'dismissed' | 'escalated'
    note TEXT,
    investigated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_investigations_domain_entity ON intelligence.anomaly_investigations(domain, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_investigations_at ON intelligence.anomaly_investigations(investigated_at DESC);

COMMENT ON TABLE intelligence.anomaly_investigations IS 'Record of anomaly review actions for pipeline monitoring';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.anomaly_investigations TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.anomaly_investigations_id_seq TO newsapp;
