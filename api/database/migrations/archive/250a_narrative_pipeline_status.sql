-- Regenerated from live Widow state — original file deleted during refactor
-- Creates intelligence.pipeline_status used by pipeline_monitoring_service

CREATE SCHEMA IF NOT EXISTS intelligence;

CREATE TABLE IF NOT EXISTS intelligence.pipeline_status (
    id          bigserial PRIMARY KEY,
    pipeline_id varchar(60)  NOT NULL,
    target_schema varchar(60) NOT NULL,
    stage       varchar(30) NOT NULL DEFAULT 'idle',
    status      varchar(20) NOT NULL DEFAULT 'completed',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    result_payload jsonb
);

CREATE INDEX IF NOT EXISTS idx_pipeline_status_pipeline_id
    ON intelligence.pipeline_status (pipeline_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_status_updated_at
    ON intelligence.pipeline_status (updated_at DESC);
