-- Add missing columns to api_cache table for smart_cache_service compatibility
ALTER TABLE api_cache
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS cache_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS size_bytes INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_api_cache_expires_at ON api_cache (expires_at);
