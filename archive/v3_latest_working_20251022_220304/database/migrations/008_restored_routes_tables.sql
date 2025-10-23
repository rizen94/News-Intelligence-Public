-- Migration 008: Create tables for restored API routes
-- Created: 2025-01-09
-- Description: Add missing tables for timeline, story management, monitoring, and intelligence features

-- Timeline Events Table
CREATE TABLE IF NOT EXISTS timeline_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id UUID NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    event_time TIME,
    source VARCHAR(200) NOT NULL,
    url TEXT,
    importance_score DECIMAL(3,2) DEFAULT 0.0 CHECK (importance_score >= 0.0 AND importance_score <= 1.0),
    event_type VARCHAR(100) NOT NULL,
    location VARCHAR(200),
    entities JSONB DEFAULT '[]'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    ml_generated BOOLEAN DEFAULT FALSE,
    confidence_score DECIMAL(3,2) DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    source_article_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for timeline_events
CREATE INDEX IF NOT EXISTS idx_timeline_events_storyline_id ON timeline_events(storyline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_date ON timeline_events(event_date);
CREATE INDEX IF NOT EXISTS idx_timeline_events_importance_score ON timeline_events(importance_score);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_type ON timeline_events(event_type);

-- Story Expectations Table (for story management)
CREATE TABLE IF NOT EXISTS story_expectations (
    story_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    priority_level INTEGER DEFAULT 5 CHECK (priority_level >= 1 AND priority_level <= 10),
    keywords JSONB DEFAULT '[]'::jsonb,
    entities JSONB DEFAULT '[]'::jsonb,
    geographic_regions JSONB DEFAULT '[]'::jsonb,
    quality_threshold DECIMAL(3,2) DEFAULT 0.7 CHECK (quality_threshold >= 0.0 AND quality_threshold <= 1.0),
    max_articles_per_day INTEGER DEFAULT 100 CHECK (max_articles_per_day > 0),
    auto_enhance BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for story_expectations
CREATE INDEX IF NOT EXISTS idx_story_expectations_is_active ON story_expectations(is_active);
CREATE INDEX IF NOT EXISTS idx_story_expectations_priority_level ON story_expectations(priority_level);

-- Story Targets Table
CREATE TABLE IF NOT EXISTS story_targets (
    target_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES story_expectations(story_id) ON DELETE CASCADE,
    target_type VARCHAR(100) NOT NULL,
    target_name VARCHAR(200) NOT NULL,
    target_description TEXT,
    importance_weight DECIMAL(3,2) DEFAULT 0.5 CHECK (importance_weight >= 0.0 AND importance_weight <= 1.0),
    tracking_keywords JSONB DEFAULT '[]'::jsonb,
    tracking_entities JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for story_targets
CREATE INDEX IF NOT EXISTS idx_story_targets_story_id ON story_targets(story_id);
CREATE INDEX IF NOT EXISTS idx_story_targets_target_type ON story_targets(target_type);

-- Story Quality Filters Table
CREATE TABLE IF NOT EXISTS story_quality_filters (
    filter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES story_expectations(story_id) ON DELETE CASCADE,
    filter_type VARCHAR(100) NOT NULL,
    filter_config JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for story_quality_filters
CREATE INDEX IF NOT EXISTS idx_story_quality_filters_story_id ON story_quality_filters(story_id);
CREATE INDEX IF NOT EXISTS idx_story_quality_filters_filter_type ON story_quality_filters(filter_type);

-- Intelligence Insights Table
CREATE TABLE IF NOT EXISTS intelligence_insights (
    insight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    insight_data JSONB NOT NULL,
    source_article_ids JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for intelligence_insights
CREATE INDEX IF NOT EXISTS idx_intelligence_insights_category ON intelligence_insights(category);
CREATE INDEX IF NOT EXISTS idx_intelligence_insights_confidence ON intelligence_insights(confidence);
CREATE INDEX IF NOT EXISTS idx_intelligence_insights_is_active ON intelligence_insights(is_active);

-- Intelligence Trends Table
CREATE TABLE IF NOT EXISTS intelligence_trends (
    trend_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    trend_type VARCHAR(50) NOT NULL,
    strength DECIMAL(3,2) NOT NULL CHECK (strength >= 0.0 AND strength <= 1.0),
    time_period VARCHAR(20) NOT NULL,
    trend_data JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for intelligence_trends
CREATE INDEX IF NOT EXISTS idx_intelligence_trends_trend_type ON intelligence_trends(trend_type);
CREATE INDEX IF NOT EXISTS idx_intelligence_trends_strength ON intelligence_trends(strength);
CREATE INDEX IF NOT EXISTS idx_intelligence_trends_is_active ON intelligence_trends(is_active);

-- Intelligence Alerts Table
CREATE TABLE IF NOT EXISTS intelligence_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    category VARCHAR(100) NOT NULL,
    alert_data JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for intelligence_alerts
CREATE INDEX IF NOT EXISTS idx_intelligence_alerts_severity ON intelligence_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_intelligence_alerts_category ON intelligence_alerts(category);
CREATE INDEX IF NOT EXISTS idx_intelligence_alerts_is_active ON intelligence_alerts(is_active);

-- ML Processing Status Table
CREATE TABLE IF NOT EXISTS ml_processing_status (
    pipeline_id VARCHAR(100) PRIMARY KEY,
    status VARCHAR(50) NOT NULL CHECK (status IN ('idle', 'running', 'completed', 'failed', 'paused')),
    progress DECIMAL(5,2) DEFAULT 0.0 CHECK (progress >= 0.0 AND progress <= 100.0),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_completion TIMESTAMP WITH TIME ZONE,
    processed_items INTEGER DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    errors JSONB DEFAULT '[]'::jsonb,
    performance_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for ml_processing_status
CREATE INDEX IF NOT EXISTS idx_ml_processing_status_status ON ml_processing_status(status);
CREATE INDEX IF NOT EXISTS idx_ml_processing_status_started_at ON ml_processing_status(started_at);

-- Weekly Digests Table
CREATE TABLE IF NOT EXISTS weekly_digests (
    digest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    total_articles_analyzed INTEGER DEFAULT 0,
    new_stories_suggested INTEGER DEFAULT 0,
    existing_stories_updated INTEGER DEFAULT 0,
    top_trending_topics JSONB DEFAULT '[]'::jsonb,
    story_suggestions JSONB DEFAULT '[]'::jsonb,
    quality_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for weekly_digests
CREATE INDEX IF NOT EXISTS idx_weekly_digests_week_start ON weekly_digests(week_start);
CREATE INDEX IF NOT EXISTS idx_weekly_digests_week_end ON weekly_digests(week_end);

-- System Monitoring Metrics Table
CREATE TABLE IF NOT EXISTS system_monitoring_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(50),
    metric_category VARCHAR(100) NOT NULL,
    tags JSONB DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for system_monitoring_metrics
CREATE INDEX IF NOT EXISTS idx_system_monitoring_metrics_name ON system_monitoring_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_system_monitoring_metrics_category ON system_monitoring_metrics(metric_category);
CREATE INDEX IF NOT EXISTS idx_system_monitoring_metrics_recorded_at ON system_monitoring_metrics(recorded_at);

-- Add foreign key constraints if they don't exist
-- Note: These will only be added if the referenced tables exist

-- Add timeline_events foreign key to storylines table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'storylines') THEN
        ALTER TABLE timeline_events 
        ADD CONSTRAINT fk_timeline_events_storyline_id 
        FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add story_targets foreign key to storylines table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'storylines') THEN
        ALTER TABLE story_targets 
        ADD CONSTRAINT fk_story_targets_story_id 
        FOREIGN KEY (story_id) REFERENCES storylines(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add story_quality_filters foreign key to storylines table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'storylines') THEN
        ALTER TABLE story_quality_filters 
        ADD CONSTRAINT fk_story_quality_filters_story_id 
        FOREIGN KEY (story_id) REFERENCES storylines(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers to all tables
CREATE TRIGGER update_timeline_events_updated_at BEFORE UPDATE ON timeline_events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_story_expectations_updated_at BEFORE UPDATE ON story_expectations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_story_targets_updated_at BEFORE UPDATE ON story_targets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_story_quality_filters_updated_at BEFORE UPDATE ON story_quality_filters FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_intelligence_insights_updated_at BEFORE UPDATE ON intelligence_insights FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_intelligence_trends_updated_at BEFORE UPDATE ON intelligence_trends FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_intelligence_alerts_updated_at BEFORE UPDATE ON intelligence_alerts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ml_processing_status_updated_at BEFORE UPDATE ON ml_processing_status FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert some sample data for testing
INSERT INTO story_expectations (name, description, priority_level, keywords, entities, geographic_regions, quality_threshold, max_articles_per_day, auto_enhance) VALUES
('Ukraine-Russia Conflict', 'Comprehensive tracking of the ongoing conflict between Ukraine and Russia', 10, '["Ukraine", "Russia", "war", "conflict", "invasion", "Zelensky", "Putin"]', '["Ukraine", "Russia", "Volodymyr Zelensky", "Vladimir Putin"]', '["Ukraine", "Russia", "Eastern Europe"]', 0.8, 200, TRUE),
('Climate Change', 'Environmental and climate-related news and developments', 8, '["climate", "environment", "global warming", "carbon", "emissions", "renewable energy"]', '["United Nations", "IPCC", "Greta Thunberg"]', '["Global"]', 0.7, 150, TRUE),
('Technology Innovation', 'Latest developments in technology and innovation', 6, '["technology", "innovation", "AI", "artificial intelligence", "machine learning", "startup"]', '["OpenAI", "Google", "Microsoft", "Apple"]', '["United States", "China", "Europe"]', 0.6, 100, TRUE)
ON CONFLICT DO NOTHING;

-- Insert sample ML processing status
INSERT INTO ml_processing_status (pipeline_id, status, progress, started_at, processed_items, total_items) VALUES
('article_classification', 'running', 75.0, NOW() - INTERVAL '15 minutes', 750, 1000),
('entity_extraction', 'completed', 100.0, NOW() - INTERVAL '1 hour', 1000, 1000),
('sentiment_analysis', 'idle', 0.0, NULL, 0, 0),
('quality_scoring', 'idle', 0.0, NULL, 0, 0)
ON CONFLICT (pipeline_id) DO NOTHING;

-- Insert sample intelligence insights
INSERT INTO intelligence_insights (title, description, category, confidence, insight_data, source_article_ids) VALUES
('High-Quality Article Spike', 'Detected 15 high-quality articles in the last hour', 'quality', 0.85, '{"count": 15, "threshold": 10, "timeframe": "1 hour"}', '[]'),
('Rising Trend: AI Technology', 'Articles about AI technology showing 40% increase over last week', 'trend', 0.78, '{"trend_direction": "rising", "percentage_increase": 40, "timeframe": "1 week"}', '[]'),
('Entity Recognition Improvement', 'Entity extraction accuracy improved by 12% this month', 'performance', 0.92, '{"improvement": 12, "metric": "accuracy", "timeframe": "1 month"}', '[]')
ON CONFLICT DO NOTHING;

-- Insert sample intelligence alerts
INSERT INTO intelligence_alerts (title, description, severity, category, alert_data) VALUES
('High Processing Error Rate', 'Detected 8 processing errors in the last hour', 'high', 'processing', '{"count": 8, "threshold": 5, "timeframe": "1 hour"}'),
('Database Connection Issue', 'Database connection timeout detected', 'critical', 'infrastructure', '{"error_type": "timeout", "duration": "30 seconds"}'),
('Low Article Quality', 'Average article quality score dropped below threshold', 'medium', 'quality', '{"avg_quality": 0.65, "threshold": 0.7}')
ON CONFLICT DO NOTHING;

-- Create a view for easy monitoring dashboard queries
CREATE OR REPLACE VIEW monitoring_dashboard_view AS
SELECT 
    'system' as metric_category,
    'cpu_usage' as metric_name,
    psutil.cpu_percent() as metric_value,
    'percent' as metric_unit,
    NOW() as recorded_at
UNION ALL
SELECT 
    'system' as metric_category,
    'memory_usage' as metric_name,
    psutil.virtual_memory().percent as metric_value,
    'percent' as metric_unit,
    NOW() as recorded_at
UNION ALL
SELECT 
    'database' as metric_category,
    'total_articles' as metric_name,
    (SELECT COUNT(*) FROM articles) as metric_value,
    'count' as metric_unit,
    NOW() as recorded_at
UNION ALL
SELECT 
    'database' as metric_category,
    'processed_articles' as metric_name,
    (SELECT COUNT(*) FROM articles WHERE status = 'processed') as metric_value,
    'count' as metric_unit,
    NOW() as recorded_at;

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO newsapp;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO newsapp;

COMMENT ON TABLE timeline_events IS 'Timeline events for storylines with ML-generated insights';
COMMENT ON TABLE story_expectations IS 'Story expectations and tracking configurations';
COMMENT ON TABLE story_targets IS 'Specific targets to track within stories';
COMMENT ON TABLE story_quality_filters IS 'Quality filters for story evaluation';
COMMENT ON TABLE intelligence_insights IS 'AI-generated insights and analysis results';
COMMENT ON TABLE intelligence_trends IS 'Trend analysis and pattern recognition results';
COMMENT ON TABLE intelligence_alerts IS 'System alerts and notifications';
COMMENT ON TABLE ml_processing_status IS 'Status of ML pipeline processing';
COMMENT ON TABLE weekly_digests IS 'Weekly analysis digests and summaries';
COMMENT ON TABLE system_monitoring_metrics IS 'System performance and monitoring metrics';

