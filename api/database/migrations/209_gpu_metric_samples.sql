-- Rolling GPU telemetry for Monitor (nvidia-smi–derived samples, aggregated hourly in API).
-- Apply on news_intel; register with api/scripts/register_applied_migration.py when deployed.

CREATE TABLE IF NOT EXISTS public.gpu_metric_samples (
    id BIGSERIAL PRIMARY KEY,
    sampled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    gpu_utilization_percent REAL,
    gpu_vram_percent REAL,
    gpu_memory_used_mb INTEGER,
    gpu_memory_total_mb INTEGER,
    gpu_temperature_c INTEGER
);

CREATE INDEX IF NOT EXISTS idx_gpu_metric_samples_sampled_at
    ON public.gpu_metric_samples (sampled_at DESC);

COMMENT ON TABLE public.gpu_metric_samples IS
    'Throttled snapshots from shared.gpu_metrics (nvidia-smi). Used for Monitor GPU/VRAM history.';
