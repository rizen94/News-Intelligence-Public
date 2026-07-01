-- Pipeline phase heartbeats for cron + nightly drain visibility (Operations / backlog_status).

CREATE TABLE IF NOT EXISTS public.pipeline_phase_heartbeats (
    phase_name VARCHAR(128) PRIMARY KEY,
    scheduler_path VARCHAR(32) NOT NULL DEFAULT 'automation',
    last_run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_success BOOLEAN NOT NULL DEFAULT true,
    items_processed INTEGER NOT NULL DEFAULT 0,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_phase_heartbeats_updated
    ON public.pipeline_phase_heartbeats (updated_at DESC);

COMMENT ON TABLE public.pipeline_phase_heartbeats IS
    'Last-run timestamps for pipeline phases (automation, cron, nightly_unified).';
