-- Migration 011: Automation and System Tables
-- Creates tables for automation pipeline, system alerts, and automation logs

-- Automation Logs table for tracking automation activities
CREATE TABLE IF NOT EXISTS automation_logs (
    id SERIAL PRIMARY KEY,
    operation VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'started',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    articles_affected INTEGER DEFAULT 0,
    processing_time FLOAT DEFAULT 0.0,
    details JSONB DEFAULT '{}',
    error_message TEXT,
    triggered_by VARCHAR(50) DEFAULT 'system'
);

-- System Alerts table for system notifications
CREATE TABLE IF NOT EXISTS system_alerts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    category VARCHAR(50) DEFAULT 'system',
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(100),
    context JSONB DEFAULT '{}'
);

-- Briefing Templates table for daily briefing management
CREATE TABLE IF NOT EXISTS briefing_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sections JSONB DEFAULT '[]',
    schedule VARCHAR(20) DEFAULT 'daily',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system'
);

-- Generated Briefings table for storing generated briefings
CREATE TABLE IF NOT EXISTS generated_briefings (
    id SERIAL PRIMARY KEY,
    template_id INTEGER REFERENCES briefing_templates(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'generated',
    article_count INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

-- Priority Rules table for content prioritization
CREATE TABLE IF NOT EXISTS priority_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    condition TEXT NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system'
);

-- Content Priority Assignments table
CREATE TABLE IF NOT EXISTS content_priority_assignments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    priority_level VARCHAR(20) NOT NULL,
    priority_score FLOAT DEFAULT 0.0,
    assigned_by VARCHAR(100) DEFAULT 'system',
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    rule_id INTEGER REFERENCES priority_rules(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'
);

-- Automation Tasks table for task management
CREATE TABLE IF NOT EXISTS automation_tasks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    schedule VARCHAR(100) NOT NULL,
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'idle',
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_execution_time FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_automation_logs_operation ON automation_logs(operation);
CREATE INDEX IF NOT EXISTS idx_automation_logs_timestamp ON automation_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_automation_logs_status ON automation_logs(status);

CREATE INDEX IF NOT EXISTS idx_system_alerts_severity ON system_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_system_alerts_resolved ON system_alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_system_alerts_created_at ON system_alerts(created_at);

CREATE INDEX IF NOT EXISTS idx_briefing_templates_enabled ON briefing_templates(enabled);
CREATE INDEX IF NOT EXISTS idx_briefing_templates_schedule ON briefing_templates(schedule);

CREATE INDEX IF NOT EXISTS idx_generated_briefings_template_id ON generated_briefings(template_id);
CREATE INDEX IF NOT EXISTS idx_generated_briefings_generated_at ON generated_briefings(generated_at);
CREATE INDEX IF NOT EXISTS idx_generated_briefings_status ON generated_briefings(status);

CREATE INDEX IF NOT EXISTS idx_priority_rules_enabled ON priority_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_priority_rules_priority ON priority_rules(priority);

CREATE INDEX IF NOT EXISTS idx_content_priority_article_id ON content_priority_assignments(article_id);
CREATE INDEX IF NOT EXISTS idx_content_priority_level ON content_priority_assignments(priority_level);
CREATE INDEX IF NOT EXISTS idx_content_priority_assigned_at ON content_priority_assignments(assigned_at);

CREATE INDEX IF NOT EXISTS idx_automation_tasks_enabled ON automation_tasks(enabled);
CREATE INDEX IF NOT EXISTS idx_automation_tasks_next_run ON automation_tasks(next_run);
CREATE INDEX IF NOT EXISTS idx_automation_tasks_status ON automation_tasks(status);

-- Create triggers for updated_at timestamps
DROP TRIGGER IF EXISTS update_briefing_templates_updated_at ON briefing_templates;
CREATE TRIGGER update_briefing_templates_updated_at
    BEFORE UPDATE ON briefing_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_priority_rules_updated_at ON priority_rules;
CREATE TRIGGER update_priority_rules_updated_at
    BEFORE UPDATE ON priority_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_automation_tasks_updated_at ON automation_tasks;
CREATE TRIGGER update_automation_tasks_updated_at
    BEFORE UPDATE ON automation_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default data
INSERT INTO briefing_templates (name, description, sections, schedule, enabled) VALUES
('Executive Summary', 'High-level overview of key developments', '["Top Stories", "Market Impact", "Key Metrics"]', 'daily', true),
('Technology Focus', 'Technology and innovation highlights', '["Tech News", "AI Developments", "Startup Updates"]', 'daily', true),
('Weekly Analysis', 'Comprehensive weekly analysis', '["Trend Analysis", "Market Review", "Forecast"]', 'weekly', true)
ON CONFLICT DO NOTHING;

INSERT INTO priority_rules (name, condition, priority, enabled) VALUES
('Breaking News', 'title ILIKE ''%breaking%'' OR title ILIKE ''%urgent%''', 'critical', true),
('High-Impact Technology', 'category = ''technology'' AND entities @> ''["AI", "artificial intelligence"]''', 'high', true),
('Financial Markets', 'category = ''business'' AND entities @> ''["stock", "market", "economy"]''', 'high', true),
('Political Developments', 'category = ''politics'' AND priority_score > 0.8', 'medium', true)
ON CONFLICT DO NOTHING;

INSERT INTO automation_tasks (name, description, schedule, enabled) VALUES
('RSS Collection', 'Collect articles from RSS feeds', 'every 15 minutes', true),
('ML Processing', 'Process articles with ML models', 'every 30 minutes', true),
('Deduplication', 'Detect and remove duplicate articles', 'every hour', true),
('Story Consolidation', 'Consolidate related articles into stories', 'every 2 hours', true),
('Daily Briefing Generation', 'Generate daily briefings', 'daily at 06:00', true),
('Database Cleanup', 'Clean up old data and optimize database', 'weekly on Sunday at 02:00', true)
ON CONFLICT DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE automation_logs IS 'Logs automation pipeline activities and operations';
COMMENT ON TABLE system_alerts IS 'System alerts and notifications for monitoring';
COMMENT ON TABLE briefing_templates IS 'Templates for generating daily briefings';
COMMENT ON TABLE generated_briefings IS 'Generated briefings based on templates';
COMMENT ON TABLE priority_rules IS 'Rules for content prioritization';
COMMENT ON TABLE content_priority_assignments IS 'Priority assignments for articles';
COMMENT ON TABLE automation_tasks IS 'Scheduled automation tasks and their status';

COMMENT ON COLUMN automation_logs.operation IS 'Type of operation: pipeline, consolidation, digest, cleanup, etc.';
COMMENT ON COLUMN automation_logs.articles_affected IS 'Number of articles affected by the operation';
COMMENT ON COLUMN automation_logs.processing_time IS 'Processing time in seconds';
COMMENT ON COLUMN automation_logs.details IS 'JSON object with operation-specific details';

COMMENT ON COLUMN system_alerts.severity IS 'Alert severity: critical, warning, info';
COMMENT ON COLUMN system_alerts.category IS 'Alert category: system, performance, security, etc.';
COMMENT ON COLUMN system_alerts.context IS 'JSON object with additional context about the alert';

COMMENT ON COLUMN briefing_templates.sections IS 'JSON array of briefing sections to include';
COMMENT ON COLUMN briefing_templates.schedule IS 'Schedule frequency: daily, weekly, monthly';

COMMENT ON COLUMN priority_rules.condition IS 'SQL-like condition for matching articles';
COMMENT ON COLUMN priority_rules.priority IS 'Priority level: critical, high, medium, low';

COMMENT ON COLUMN content_priority_assignments.priority_score IS 'Calculated priority score (0.0-1.0)';
COMMENT ON COLUMN content_priority_assignments.rule_id IS 'ID of the priority rule that triggered this assignment';

COMMENT ON COLUMN automation_tasks.schedule IS 'Cron-like schedule expression';
COMMENT ON COLUMN automation_tasks.next_run IS 'Next scheduled execution time';
COMMENT ON COLUMN automation_tasks.avg_execution_time IS 'Average execution time in seconds';
