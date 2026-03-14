-- Migration 150: Finance research topics (saved analyses for continual refinement)
-- A research topic is created from a completed analysis and can be refined by re-running research.

CREATE TABLE IF NOT EXISTS finance.research_topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    query TEXT NOT NULL,
    topic VARCHAR(50) NOT NULL DEFAULT 'gold',
    date_range_start DATE,
    date_range_end DATE,
    summary TEXT,
    source_task_id VARCHAR(64),
    last_refined_task_id VARCHAR(64),
    last_refined_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_finance_research_topics_updated
    ON finance.research_topics(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_finance_research_topics_name
    ON finance.research_topics(name);

COMMENT ON TABLE finance.research_topics IS 'Saved finance analyses that can be refined over time by re-running research';
