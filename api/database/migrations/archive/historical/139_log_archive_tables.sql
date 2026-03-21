-- Log archive tables: store local JSONL logs on NAS PostgreSQL
-- Populated by scripts/log_archive_to_nas.py (2x daily cron)
-- Keeps local disk from filling; enables querying logs on NAS

-- Unified archive: one row per log entry, source identifies log type
CREATE TABLE IF NOT EXISTS log_archive (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    entry JSONB NOT NULL,
    logged_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_log_archive_source ON log_archive(source);
CREATE INDEX IF NOT EXISTS idx_log_archive_logged_at ON log_archive(logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_archive_task_id ON log_archive((entry->>'task_id')) WHERE entry->>'task_id' IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_log_archive_request_id ON log_archive((entry->>'request_id')) WHERE entry->>'request_id' IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_log_archive_component ON log_archive((entry->>'component')) WHERE entry->>'component' IS NOT NULL;

COMMENT ON TABLE log_archive IS 'Archived logs from local JSONL files; moved to NAS 2x/day via cron';
