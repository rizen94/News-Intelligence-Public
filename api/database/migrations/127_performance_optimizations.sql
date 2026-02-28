-- Performance Optimization Migration
-- Adds composite indexes and optimizations for common query patterns

-- Composite indexes for articles (domain-aware)
-- These indexes are created per domain schema for better query performance

DO $$
DECLARE
    domain_schema TEXT;
BEGIN
    -- Loop through all domain schemas
    FOR domain_schema IN SELECT domains.schema_name FROM domains WHERE domains.is_active = true
    LOOP
        -- Composite index for articles by created_at and processing_status (common dashboard query)
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_articles_created_status ON %I.articles(created_at DESC, processing_status)', 
                       domain_schema, domain_schema);
        
        -- Composite index for articles by source_domain and created_at (common filtering)
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_articles_source_created ON %I.articles(source_domain, created_at DESC)', 
                       domain_schema, domain_schema);
        
        -- Composite index for articles by quality_score and created_at (quality filtering)
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_articles_quality_created ON %I.articles(quality_score DESC, created_at DESC) WHERE quality_score IS NOT NULL', 
                       domain_schema, domain_schema);
        
        -- Index for URL lookups (duplicate detection)
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_articles_url ON %I.articles(url) WHERE url IS NOT NULL', 
                       domain_schema, domain_schema);
        
        -- Index for content_hash lookups (deduplication)
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_articles_content_hash ON %I.articles(content_hash) WHERE content_hash IS NOT NULL', 
                       domain_schema, domain_schema);
        
        -- Composite index for storylines by status and updated_at
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_storylines_status_updated ON %I.storylines(status, updated_at DESC)', 
                       domain_schema, domain_schema);
        
        -- Index for RSS feeds by is_active and last_fetched_at
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_rss_feeds_active_fetched ON %I.rss_feeds(is_active, last_fetched_at) WHERE is_active = true', 
                       domain_schema, domain_schema);
        
        RAISE NOTICE 'Created performance indexes for schema: %', domain_schema;
    END LOOP;
END $$;

-- Global indexes (for system_monitoring queries)
-- These help with cross-domain aggregation queries

-- Index for system_alerts (frequently queried)
CREATE INDEX IF NOT EXISTS idx_system_alerts_active_severity 
ON system_alerts(is_active, severity, created_at DESC) 
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_system_alerts_severity_created 
ON system_alerts(severity, created_at DESC);

-- Analyze tables to update statistics (helps query planner)
DO $$
DECLARE
    domain_schema TEXT;
BEGIN
    FOR domain_schema IN SELECT domains.schema_name FROM domains WHERE domains.is_active = true
    LOOP
        EXECUTE format('ANALYZE %I.articles', domain_schema);
        EXECUTE format('ANALYZE %I.storylines', domain_schema);
        EXECUTE format('ANALYZE %I.rss_feeds', domain_schema);
        RAISE NOTICE 'Analyzed tables for schema: %', domain_schema;
    END LOOP;
END $$;

-- Analyze system tables
ANALYZE system_alerts;

