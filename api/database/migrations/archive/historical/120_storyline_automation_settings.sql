-- Storyline Automation Settings Migration
-- Adds automation controls for RAG-enhanced article discovery

-- Add automation settings columns to storylines table
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS automation_enabled BOOLEAN DEFAULT false;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS automation_mode VARCHAR(50) DEFAULT 'manual' CHECK (automation_mode IN ('disabled', 'manual', 'auto_approve', 'review_queue'));
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS automation_settings JSONB DEFAULT '{}'::jsonb;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS search_keywords TEXT[] DEFAULT '{}';
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS search_entities TEXT[] DEFAULT '{}';
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS search_exclude_keywords TEXT[] DEFAULT '{}';
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS last_automation_run TIMESTAMP WITH TIME ZONE;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS automation_frequency_hours INTEGER DEFAULT 24;

-- Create table for article suggestions queue (review before adding)
CREATE TABLE IF NOT EXISTS storyline_article_suggestions (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    
    -- Relevance metrics
    relevance_score DECIMAL(3,2) DEFAULT 0.0,
    semantic_score DECIMAL(3,2) DEFAULT 0.0,
    keyword_score DECIMAL(3,2) DEFAULT 0.0,
    quality_score DECIMAL(3,2) DEFAULT 0.0,
    combined_score DECIMAL(3,2) DEFAULT 0.0,
    
    -- Matching criteria
    matched_keywords TEXT[] DEFAULT '{}',
    matched_entities TEXT[] DEFAULT '{}',
    reasoning TEXT,  -- Why this article was suggested
    
    -- Status and approval
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'added', 'expired')),
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes TEXT,
    
    -- Metadata
    suggested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    suggested_by VARCHAR(100) DEFAULT 'automation',
    expires_at TIMESTAMP WITH TIME ZONE,  -- Auto-expire old suggestions
    
    -- Constraints
    UNIQUE(storyline_id, article_id),
    CONSTRAINT chk_suggestion_scores CHECK (
        relevance_score >= 0.0 AND relevance_score <= 1.0 AND
        semantic_score >= 0.0 AND semantic_score <= 1.0 AND
        keyword_score >= 0.0 AND keyword_score <= 1.0 AND
        quality_score >= 0.0 AND quality_score <= 1.0 AND
        combined_score >= 0.0 AND combined_score <= 1.0
    )
);

-- Create table for automation history/logs
CREATE TABLE IF NOT EXISTS storyline_automation_log (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    
    -- Execution details
    execution_type VARCHAR(50) NOT NULL CHECK (execution_type IN ('discovery', 'auto_add', 'suggestion_generation')),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    -- Results
    articles_found INTEGER DEFAULT 0,
    articles_suggested INTEGER DEFAULT 0,
    articles_added INTEGER DEFAULT 0,
    articles_rejected INTEGER DEFAULT 0,
    
    -- Configuration used
    config_snapshot JSONB DEFAULT '{}'::jsonb,
    
    -- Status
    status VARCHAR(50) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    error_message TEXT,
    
    -- Metadata
    triggered_by VARCHAR(100) DEFAULT 'automation',  -- 'automation', 'manual', 'api'
    
    CONSTRAINT chk_duration CHECK (duration_seconds >= 0)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_storyline_automation_enabled ON storylines(automation_enabled) WHERE automation_enabled = true;
CREATE INDEX IF NOT EXISTS idx_storyline_automation_mode ON storylines(automation_mode);
CREATE INDEX IF NOT EXISTS idx_storyline_article_suggestions_storyline ON storyline_article_suggestions(storyline_id, status);
CREATE INDEX IF NOT EXISTS idx_storyline_article_suggestions_pending ON storyline_article_suggestions(storyline_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_storyline_article_suggestions_score ON storyline_article_suggestions(storyline_id, combined_score DESC);
CREATE INDEX IF NOT EXISTS idx_storyline_automation_log_storyline ON storyline_automation_log(storyline_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_storyline_automation_log_status ON storyline_automation_log(status, started_at DESC);

-- Add comments for documentation
COMMENT ON COLUMN storylines.automation_enabled IS 'Whether automation is enabled for this storyline';
COMMENT ON COLUMN storylines.automation_mode IS 'Automation mode: disabled, manual (suggestions only), auto_approve (auto-add above threshold), review_queue (suggestions require review)';
COMMENT ON COLUMN storylines.automation_settings IS 'JSON configuration: min_relevance_score, min_quality_score, max_articles_per_run, date_range_days, source_filters, etc.';
COMMENT ON COLUMN storylines.search_keywords IS 'Keywords to search for when discovering articles';
COMMENT ON COLUMN storylines.search_entities IS 'Entities (people, organizations, locations) to search for';
COMMENT ON COLUMN storylines.search_exclude_keywords IS 'Keywords to exclude from results';
COMMENT ON COLUMN storylines.automation_frequency_hours IS 'How often to run automation (hours)';
COMMENT ON TABLE storyline_article_suggestions IS 'Articles suggested for addition to storylines, pending review or auto-approval';
COMMENT ON TABLE storyline_automation_log IS 'History of automation runs for audit and debugging';

