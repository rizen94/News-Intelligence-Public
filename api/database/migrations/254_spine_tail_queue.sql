-- Migration 254: Global spine_tail_queue for spine_sql_tail sub-steps (v10.1)

BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.spine_tail_queue (
    id BIGSERIAL PRIMARY KEY,
    schema_name VARCHAR(80) NOT NULL,
    article_id BIGINT,
    context_id BIGINT,
    job_type VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    priority INTEGER NOT NULL DEFAULT 2,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_spine_tail_q_pending
    ON intelligence.spine_tail_queue (job_type, priority DESC, created_at ASC)
    WHERE status = 'pending';

COMMENT ON TABLE intelligence.spine_tail_queue IS
    'Work queue for spine_sql_tail sub-steps: profile_link, fast_topic, link_indexer, etc.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.spine_tail_queue TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.spine_tail_queue_id_seq TO newsapp;

COMMIT;
