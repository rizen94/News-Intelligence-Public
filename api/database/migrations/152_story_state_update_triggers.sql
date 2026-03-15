-- Migration 152: Story state update triggers — fact_change_log, story_update_queue, trigger on versioned_facts
-- See docs/STORY_STATE_UPDATE_TRIGGERS.md. Application processes log and enqueues story updates per domain.

CREATE SCHEMA IF NOT EXISTS intelligence;
GRANT USAGE ON SCHEMA intelligence TO newsapp;

-- Log each new/updated fact for application to resolve to affected storylines
CREATE TABLE IF NOT EXISTS intelligence.fact_change_log (
    id SERIAL PRIMARY KEY,
    fact_id INTEGER NOT NULL,
    entity_profile_id INTEGER NOT NULL,
    change_type VARCHAR(50) NOT NULL DEFAULT 'new_fact',
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    story_updates_triggered INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fact_change_log_processed ON intelligence.fact_change_log(processed) WHERE processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_fact_change_log_changed ON intelligence.fact_change_log(changed_at DESC);

COMMENT ON TABLE intelligence.fact_change_log IS 'Log of versioned_facts changes; app resolves entity_profile to domain+storylines and enqueues story_update_queue';

-- Queue of (domain, storyline_id) to be processed for state update
CREATE TABLE IF NOT EXISTS intelligence.story_update_queue (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    storyline_id INTEGER NOT NULL,
    trigger_type VARCHAR(50) NOT NULL DEFAULT 'new_fact',
    trigger_id VARCHAR(100),
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_story_update_queue_processed ON intelligence.story_update_queue(processed) WHERE processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_story_update_queue_priority_created ON intelligence.story_update_queue(priority, created_at);
CREATE INDEX IF NOT EXISTS idx_story_update_queue_domain_story ON intelligence.story_update_queue(domain_key, storyline_id);

COMMENT ON TABLE intelligence.story_update_queue IS 'Queue of (domain_key, storyline_id) to refresh story state; no FK to storylines (cross-schema)';

-- Trigger: on INSERT into versioned_facts, log to fact_change_log
CREATE OR REPLACE FUNCTION intelligence.trigger_fact_change_log()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO intelligence.fact_change_log (fact_id, entity_profile_id, change_type)
    VALUES (NEW.id, NEW.entity_profile_id, 'new_fact');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS versioned_facts_after_insert ON intelligence.versioned_facts;
CREATE TRIGGER versioned_facts_after_insert
    AFTER INSERT ON intelligence.versioned_facts
    FOR EACH ROW
    EXECUTE FUNCTION intelligence.trigger_fact_change_log();

GRANT SELECT, INSERT, UPDATE ON intelligence.fact_change_log TO newsapp;
GRANT SELECT, INSERT, UPDATE ON intelligence.story_update_queue TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.fact_change_log_id_seq TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.story_update_queue_id_seq TO newsapp;
