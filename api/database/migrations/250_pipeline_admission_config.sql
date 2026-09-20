-- Migration 250: Adaptive signal admission threshold persistence (v10.1)

BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.pipeline_admission_config (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    full_min_quality DOUBLE PRECISION NOT NULL DEFAULT 0.45,
    target_ratio_min DOUBLE PRECISION NOT NULL DEFAULT 0.15,
    target_ratio_max DOUBLE PRECISION NOT NULL DEFAULT 0.35,
    net_growth_7d DOUBLE PRECISION,
    signal_ratio_7d DOUBLE PRECISION,
    consecutive_growth_days INT NOT NULL DEFAULT 0,
    consecutive_shrink_days INT NOT NULL DEFAULT 0,
    last_adjusted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO intelligence.pipeline_admission_config (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE intelligence.pipeline_admission_config IS
    'Adaptive ARTICLE_SIGNAL_FULL_MIN_QUALITY controller state; read by article_signal_gate.';

GRANT SELECT, UPDATE ON intelligence.pipeline_admission_config TO newsapp;

COMMIT;
