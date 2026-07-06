-- Migration 249: Optional runtime overrides for feature registry (YAML remains SSOT)

BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.feature_registry_overrides (
    feature_key VARCHAR(120) PRIMARY KEY,
    enabled BOOLEAN,
    lifecycle VARCHAR(40),
    notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(120) DEFAULT 'system'
);

COMMENT ON TABLE intelligence.feature_registry_overrides IS
    'Runtime overrides for api/config/features.yaml; ops emergency toggles without redeploy.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.feature_registry_overrides TO newsapp;

COMMIT;
