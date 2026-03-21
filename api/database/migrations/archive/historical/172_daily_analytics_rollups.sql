-- Daily rollups for long-term analytics (automation runs + archived log volume)
-- Populate via scripts/run_daily_analytics_rollup.py (typically daily)

-- Per-phase automation run counts/durations aggregated by UTC day.
CREATE TABLE IF NOT EXISTS automation_run_history_daily (
    day DATE NOT NULL,
    phase_name VARCHAR(100) NOT NULL,

    run_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,

    avg_duration_seconds DOUBLE PRECISION,
    total_duration_seconds DOUBLE PRECISION,

    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (day, phase_name)
);

CREATE INDEX IF NOT EXISTS idx_automation_run_history_daily_phase ON automation_run_history_daily(phase_name);
CREATE INDEX IF NOT EXISTS idx_automation_run_history_daily_day ON automation_run_history_daily(day DESC);

-- Per-source archived log volume aggregated by UTC day.
-- This is derived from log_archive.logged_at and log_archive.entry->>'level' (when present).
CREATE TABLE IF NOT EXISTS log_archive_daily_rollup (
    day DATE NOT NULL,
    source VARCHAR(50) NOT NULL,

    total_entries INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    info_count INTEGER NOT NULL DEFAULT 0,
    debug_count INTEGER NOT NULL DEFAULT 0,

    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (day, source)
);

CREATE INDEX IF NOT EXISTS idx_log_archive_daily_rollup_source ON log_archive_daily_rollup(source);
CREATE INDEX IF NOT EXISTS idx_log_archive_daily_rollup_day ON log_archive_daily_rollup(day DESC);

