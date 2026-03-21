-- Migration 181: Durable storyline narratives + content refinement queue
-- - Domain storylines: canonical 70B narrative, cached timeline narratives (8B path)
-- - intelligence.content_refinement_queue: user/automation requests processed by workers (not ad-hoc HTTP LLM)

CREATE SCHEMA IF NOT EXISTS intelligence;

CREATE TABLE IF NOT EXISTS intelligence.content_refinement_queue (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    storyline_id INTEGER NOT NULL,
    job_type VARCHAR(80) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('high', 'medium', 'low')),
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_content_refinement_queue_pending
    ON intelligence.content_refinement_queue (status, priority, created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_content_refinement_queue_domain_story
    ON intelligence.content_refinement_queue (domain_key, storyline_id, created_at DESC);

-- At most one pending row per (domain, storyline, job_type)
CREATE UNIQUE INDEX IF NOT EXISTS idx_content_refinement_pending_unique
    ON intelligence.content_refinement_queue (domain_key, storyline_id, job_type)
    WHERE status = 'pending';

COMMENT ON TABLE intelligence.content_refinement_queue IS
    'Background jobs for storyline RAG analysis, 70B narrative finisher, and timeline narrative synthesis; API/UI enqueue only.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.content_refinement_queue TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.content_refinement_queue_id_seq TO newsapp;

-- Per-domain storyline columns (politics, finance, science_tech)
DO $$
DECLARE
    s text;
BEGIN
    FOREACH s IN ARRAY ARRAY['politics', 'finance', 'science_tech']
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS canonical_narrative TEXT',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS narrative_finisher_model VARCHAR(120)',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS narrative_finisher_at TIMESTAMP WITH TIME ZONE',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS narrative_finisher_meta JSONB DEFAULT ''{}''::jsonb',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS timeline_narrative_chronological TEXT',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS timeline_narrative_briefing TEXT',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS timeline_narrative_chronological_at TIMESTAMP WITH TIME ZONE',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS timeline_narrative_briefing_at TIMESTAMP WITH TIME ZONE',
            s
        );
    END LOOP;
END $$;
