-- Migration 149: Historic context orchestrator — multi-source historic data with agreement scoring
-- Requests drive parallel fetches; findings stored per source; events derived with agreement count;
-- expansions allow re-query when a prior significant event is discovered.

CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;

-- One "request" per user/question: query, date range, trigger (e.g. analysis, storyline), status
CREATE TABLE IF NOT EXISTS intelligence.historic_context_requests (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    topic VARCHAR(100),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    trigger_type VARCHAR(50) DEFAULT 'analysis',  -- analysis, storyline, manual
    trigger_id VARCHAR(255),                       -- e.g. task_id, storyline_id
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, partial
    summary TEXT,                                  -- final summarized context (after agreement + expansion)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_historic_context_requests_status ON intelligence.historic_context_requests(status);
CREATE INDEX IF NOT EXISTS idx_historic_context_requests_dates ON intelligence.historic_context_requests(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_historic_context_requests_trigger ON intelligence.historic_context_requests(trigger_type, trigger_id);

-- Raw findings per source per request (diverse sources, stored for cross-check)
CREATE TABLE IF NOT EXISTS intelligence.historic_context_findings (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES intelligence.historic_context_requests(id) ON DELETE CASCADE,
    source_id VARCHAR(50) NOT NULL,   -- news_api, wikipedia, edgar, fred, etc.
    title TEXT,
    snippet TEXT NOT NULL,
    url TEXT,
    source_date DATE,                 -- event/publication date when known
    relevance_score DECIMAL(3,2) CHECK (relevance_score >= 0 AND relevance_score <= 1),
    raw_response JSONB DEFAULT '{}',  -- optional full payload for debugging
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_historic_context_findings_request ON intelligence.historic_context_findings(request_id);
CREATE INDEX IF NOT EXISTS idx_historic_context_findings_source ON intelligence.historic_context_findings(source_id);

-- Distilled events with cross-source agreement (more sources = higher confidence)
CREATE TABLE IF NOT EXISTS intelligence.historic_context_events (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES intelligence.historic_context_requests(id) ON DELETE CASCADE,
    event_summary TEXT NOT NULL,
    date_approx DATE,                 -- best-effort event date
    source_ids TEXT[] NOT NULL DEFAULT '{}',  -- which sources mentioned this event
    agreement_count INTEGER NOT NULL DEFAULT 1 CHECK (agreement_count >= 1),
    significance_score DECIMAL(3,2) CHECK (significance_score >= 0 AND significance_score <= 1),
    finding_ids INTEGER[] DEFAULT '{}',  -- links to historic_context_findings.id for provenance
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_historic_context_events_request ON intelligence.historic_context_events(request_id);
CREATE INDEX IF NOT EXISTS idx_historic_context_events_agreement ON intelligence.historic_context_events(agreement_count DESC);

-- Expansion: when we discover a prior significant event, we spawn a child request for more detail
CREATE TABLE IF NOT EXISTS intelligence.historic_context_expansions (
    id SERIAL PRIMARY KEY,
    parent_request_id INTEGER NOT NULL REFERENCES intelligence.historic_context_requests(id) ON DELETE CASCADE,
    child_request_id INTEGER NOT NULL REFERENCES intelligence.historic_context_requests(id) ON DELETE CASCADE,
    trigger_reason VARCHAR(100) NOT NULL,  -- significant_prior_event, gap_detected, etc.
    trigger_event_id INTEGER REFERENCES intelligence.historic_context_events(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(child_request_id)
);

CREATE INDEX IF NOT EXISTS idx_historic_context_expansions_parent ON intelligence.historic_context_expansions(parent_request_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.historic_context_requests TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.historic_context_findings TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.historic_context_events TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.historic_context_expansions TO newsapp;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intelligence TO newsapp;

COMMENT ON TABLE intelligence.historic_context_requests IS 'One request per historic context question; drives parallel multi-source fetch';
COMMENT ON TABLE intelligence.historic_context_findings IS 'Raw findings per source; relevance-filtered; used for agreement scoring';
COMMENT ON TABLE intelligence.historic_context_events IS 'Distilled events; agreement_count = number of sources that mentioned it';
COMMENT ON TABLE intelligence.historic_context_expansions IS 'Child requests when orchestrator discovers prior significant event and re-queries for more detail';
