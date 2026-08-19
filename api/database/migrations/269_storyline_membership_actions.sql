-- Migration 269: storyline membership review action queue
-- Mid-band / dry-run decoupling actions for storyline article unlink, relevance demote,
-- graph quarantine, SEI demote, and tracked_event unlink.

CREATE TABLE IF NOT EXISTS intelligence.storyline_membership_actions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    domain_key TEXT NOT NULL,
    storyline_id BIGINT NOT NULL,
    article_id BIGINT,
    entity_name TEXT,
    tracked_event_id BIGINT,
    graph_left_kind TEXT,
    graph_left_id BIGINT,
    graph_right_kind TEXT,
    graph_right_id BIGINT,
    action TEXT NOT NULL
        CHECK (action IN (
            'unlink',
            'demote_relevance',
            'quarantine_graph',
            'demote_entity',
            'unlink_tracked_event'
        )),
    fit_score DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'applied', 'rejected', 'skipped')),
    rationale TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_storyline_membership_actions_pending
    ON intelligence.storyline_membership_actions (domain_key, status, created_at DESC)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_storyline_membership_actions_storyline
    ON intelligence.storyline_membership_actions (domain_key, storyline_id, created_at DESC);

COMMENT ON TABLE intelligence.storyline_membership_actions IS
    'Queue/audit for storyline membership review: unlink/demote articles and soft-deprioritize connections.';
