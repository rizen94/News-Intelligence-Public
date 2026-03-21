-- Migration 140: Orchestration schema for Newsroom Orchestrator v6
-- Event bus, task queue, investigations, source plugins, processing state.
-- entity_ids in investigations are scoped to domain_key (that domain's entity_canonical/article_entities).

CREATE SCHEMA IF NOT EXISTS orchestration;

GRANT USAGE ON SCHEMA orchestration TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA orchestration GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO newsapp;

-- Events (append-only audit; retention job can prune old rows)
CREATE TABLE orchestration.events (
    id SERIAL PRIMARY KEY,
    event_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    priority INTEGER DEFAULT 3,
    deduplication_key VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_orchestration_events_type ON orchestration.events(event_type);
CREATE INDEX idx_orchestration_events_created_at ON orchestration.events(created_at DESC);
CREATE INDEX idx_orchestration_events_dedup ON orchestration.events(deduplication_key) WHERE deduplication_key IS NOT NULL;

-- Dead letter after max retries
CREATE TABLE orchestration.events_failed (
    id SERIAL PRIMARY KEY,
    event_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    error TEXT,
    failed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX idx_orchestration_events_failed_failed_at ON orchestration.events_failed(failed_at DESC);

-- Processed events (idempotency: deduplication_key already handled)
CREATE TABLE orchestration.processed_events (
    id SERIAL PRIMARY KEY,
    deduplication_key VARCHAR(255) UNIQUE NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orchestration_processed_events_key ON orchestration.processed_events(deduplication_key);

-- Investigations: entity_ids are for domain_key's schema only
CREATE TABLE orchestration.investigations (
    id SERIAL PRIMARY KEY,
    trigger_event_id INTEGER REFERENCES orchestration.events(id),
    status VARCHAR(50) DEFAULT 'open',
    domain_key VARCHAR(50) NOT NULL,
    entity_ids INTEGER[],
    pattern_confidence DECIMAL(3,2),
    notes JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orchestration_investigations_status ON orchestration.investigations(status);
CREATE INDEX idx_orchestration_investigations_domain ON orchestration.investigations(domain_key);

-- Workflows (optional config/metadata)
CREATE TABLE orchestration.workflows (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Task queue (durable queue; optional use)
CREATE TABLE orchestration.task_queue (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    priority INTEGER DEFAULT 3,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_orchestration_task_queue_status_priority ON orchestration.task_queue(status, priority);

-- Source plugins config (per-type config)
CREATE TABLE orchestration.source_plugins (
    id SERIAL PRIMARY KEY,
    plugin_type VARCHAR(50) NOT NULL,
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched_at TIMESTAMP WITH TIME ZONE
);

-- Key-value state
CREATE TABLE orchestration.processing_state (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA orchestration TO newsapp;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA orchestration TO newsapp;

COMMENT ON TABLE orchestration.investigations IS 'entity_ids refer to entity_canonical/article_entities in schema for domain_key';
COMMENT ON TABLE orchestration.events IS 'Append-only event log; retention job can delete rows older than 7 days';
