-- API Cache Table for News Intelligence System
-- Migration 011: Add API caching support

-- Create API cache table
CREATE TABLE IF NOT EXISTS api_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(64) NOT NULL,
    service VARCHAR(50) NOT NULL,
    query TEXT NOT NULL,
    response_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Composite unique constraint
    UNIQUE(cache_key, service)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_api_cache_service_key 
ON api_cache (service, cache_key);

CREATE INDEX IF NOT EXISTS idx_api_cache_created_at 
ON api_cache (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_cache_service_created 
ON api_cache (service, created_at DESC);

-- Add summary versioning table
CREATE TABLE IF NOT EXISTS storyline_summary_versions (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    version_number INTEGER NOT NULL,
    summary_type VARCHAR(50) NOT NULL, -- 'basic', 'rag_enhanced'
    summary_content TEXT NOT NULL,
    rag_context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) DEFAULT 'system',
    
    FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE
);

-- Create indexes for summary versions
CREATE INDEX IF NOT EXISTS idx_storyline_summary_versions_storyline_id 
ON storyline_summary_versions (storyline_id);

CREATE INDEX IF NOT EXISTS idx_storyline_summary_versions_created_at 
ON storyline_summary_versions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_storyline_summary_versions_type 
ON storyline_summary_versions (summary_type);

-- Add API usage tracking table
CREATE TABLE IF NOT EXISTS api_usage_tracking (
    id SERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    request_count INTEGER DEFAULT 1,
    response_size INTEGER DEFAULT 0,
    processing_time_ms INTEGER DEFAULT 0,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for usage tracking
CREATE INDEX IF NOT EXISTS idx_api_usage_tracking_service 
ON api_usage_tracking (service);

CREATE INDEX IF NOT EXISTS idx_api_usage_tracking_created_at 
ON api_usage_tracking (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_usage_tracking_success 
ON api_usage_tracking (success);

-- Add summary enhancement tracking to storylines table
ALTER TABLE storylines 
ADD COLUMN IF NOT EXISTS last_basic_summary_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS last_rag_enhancement_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS summary_version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS enhancement_count INTEGER DEFAULT 0;

-- Create index for enhancement tracking
CREATE INDEX IF NOT EXISTS idx_storylines_enhancement_tracking 
ON storylines (last_basic_summary_at, last_rag_enhancement_at, enhancement_count);


