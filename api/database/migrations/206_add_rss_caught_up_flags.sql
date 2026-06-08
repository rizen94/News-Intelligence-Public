-- Migration: Add RSS caught-up flags
-- Date: 2026-05-11

-- Add caught-up tracking columns to rss_feeds tables in all domain schemas
DO $$
DECLARE
    schema_name text;
BEGIN
    -- Get all domain schemas
    FOR schema_name IN 
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'public')
        AND schema_name NOT LIKE 'pg_toast%'
        AND schema_name NOT LIKE 'pg_temp%'
        AND schema_name LIKE '%_domain'
    LOOP
        -- Check if rss_feeds table exists in this schema
        IF EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_schema = schema_name 
            AND table_name = 'rss_feeds'
        ) THEN
            -- Add the new columns if they don't exist
            EXECUTE format('
                ALTER TABLE %I.rss_feeds 
                ADD COLUMN IF NOT EXISTS is_caught_up BOOLEAN DEFAULT FALSE;
            ', schema_name);
            
            EXECUTE format('
                ALTER TABLE %I.rss_feeds 
                ADD COLUMN IF NOT EXISTS caught_up_since TIMESTAMP;
            ', schema_name);
            
            EXECUTE format('
                ALTER TABLE %I.rss_feeds 
                ADD COLUMN IF NOT EXISTS last_caught_up_check TIMESTAMP;
            ', schema_name);
            
            -- Create indexes for better performance
            EXECUTE format('
                CREATE INDEX IF NOT EXISTS idx_%I_rss_feeds_caught_up ON %I.rss_feeds(is_caught_up);
            ', schema_name, schema_name);
            
            EXECUTE format('
                CREATE INDEX IF NOT EXISTS idx_%I_rss_feeds_caught_up_since ON %I.rss_feeds(caught_up_since);
            ', schema_name, schema_name);
            
            RAISE NOTICE 'Added caught-up flags to % schema', schema_name;
        END IF;
    END LOOP;
END $$;

-- Add indexes to public schema if they don't exist
ALTER TABLE public.rss_feeds 
ADD COLUMN IF NOT EXISTS is_caught_up BOOLEAN DEFAULT FALSE;

ALTER TABLE public.rss_feeds 
ADD COLUMN IF NOT EXISTS caught_up_since TIMESTAMP;

ALTER TABLE public.rss_feeds 
ADD COLUMN IF NOT EXISTS last_caught_up_check TIMESTAMP;

-- Create indexes for public schema
CREATE INDEX IF NOT EXISTS idx_rss_feeds_caught_up ON public.rss_feeds(is_caught_up);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_caught_up_since ON public.rss_feeds(caught_up_since);

-- Add comments for documentation
COMMENT ON COLUMN public.rss_feeds.is_caught_up IS 'Flag indicating if feed has caught up with no new articles';
COMMENT ON COLUMN public.rss_feeds.caught_up_since IS 'Timestamp when feed was marked as caught up';
COMMENT ON COLUMN public.rss_feeds.last_caught_up_check IS 'Timestamp of last caught-up status check';