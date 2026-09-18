-- Migration 303: Pulse digest snapshots (audit/history; live read uses compute_pulse)

CREATE TABLE IF NOT EXISTS intelligence.pulse_snapshots (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_hours INTEGER NOT NULL DEFAULT 48,
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_pulse_snapshots_created
    ON intelligence.pulse_snapshots (created_at DESC);

COMMENT ON TABLE intelligence.pulse_snapshots IS
    'Historical pulse ranking snapshots from run_pulse_digest.py';

DO $$
BEGIN
    RAISE NOTICE 'Migration 303: pulse_snapshots';
END $$;
