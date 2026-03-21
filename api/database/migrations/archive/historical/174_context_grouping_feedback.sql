-- Human judgments: does this context belong with a topic/storyline/pattern grouping?
-- Feeds future synthesis tuning; see docs/UI_PIPELINE_AUDIT_GUIDE.md (if present).

CREATE TABLE IF NOT EXISTS intelligence.context_grouping_feedback (
    id SERIAL PRIMARY KEY,
    context_id INTEGER NOT NULL REFERENCES intelligence.contexts(id) ON DELETE CASCADE,
    grouping_type VARCHAR(50) NOT NULL
        CHECK (grouping_type IN ('topic', 'storyline', 'pattern', 'other')),
    grouping_id INTEGER,
    grouping_label TEXT,
    judgment VARCHAR(20) NOT NULL
        CHECK (judgment IN ('belongs', 'does_not_belong', 'unsure')),
    notes TEXT,
    judged_by TEXT,
    judged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_context_grouping_feedback_context
    ON intelligence.context_grouping_feedback (context_id, judged_at DESC);

CREATE INDEX IF NOT EXISTS idx_context_grouping_feedback_grouping
    ON intelligence.context_grouping_feedback (grouping_type, grouping_id);

COMMENT ON TABLE intelligence.context_grouping_feedback IS
    'Analyst feedback: whether a context belongs with a topic/storyline/pattern; for reliability audits and model tuning.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.context_grouping_feedback TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.context_grouping_feedback_id_seq TO newsapp;
