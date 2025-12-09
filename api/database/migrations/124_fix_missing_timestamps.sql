-- Migration 124: Fix Missing Timestamp Columns
-- Adds created_at and updated_at to tables that are missing them
-- Created: December 7, 2025
-- Version: 4.0.2

-- ============================================================================
-- ADD MISSING TIMESTAMP COLUMNS
-- ============================================================================

-- Function to add missing timestamps to a table
CREATE OR REPLACE FUNCTION add_missing_timestamps(schema_name TEXT, table_name TEXT)
RETURNS VOID AS $$
DECLARE
    has_created_at BOOLEAN;
    has_updated_at BOOLEAN;
BEGIN
    -- Check if created_at exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = schema_name
        AND information_schema.columns.table_name = add_missing_timestamps.table_name
        AND column_name = 'created_at'
    ) INTO has_created_at;
    
    -- Check if updated_at exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = schema_name
        AND information_schema.columns.table_name = add_missing_timestamps.table_name
        AND column_name = 'updated_at'
    ) INTO has_updated_at;
    
    -- Add created_at if missing
    IF NOT has_created_at THEN
        EXECUTE format('
            ALTER TABLE %I.%I
            ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        ', schema_name, table_name);
        RAISE NOTICE 'Added created_at to %.%', schema_name, table_name;
    END IF;
    
    -- Add updated_at if missing
    IF NOT has_updated_at THEN
        EXECUTE format('
            ALTER TABLE %I.%I
            ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        ', schema_name, table_name);
        RAISE NOTICE 'Added updated_at to %.%', schema_name, table_name;
        
        -- Add trigger for updated_at
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%I_%I_updated_at ON %I.%I;
            CREATE TRIGGER update_%I_%I_updated_at
            BEFORE UPDATE ON %I.%I
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        ', schema_name, table_name, schema_name, table_name,
           schema_name, table_name, schema_name, table_name);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Add timestamps to all domain schemas
SELECT add_missing_timestamps('politics', 'rss_feeds');
SELECT add_missing_timestamps('politics', 'storyline_articles');
SELECT add_missing_timestamps('politics', 'topic_cluster_memberships');
SELECT add_missing_timestamps('politics', 'topic_clusters');
SELECT add_missing_timestamps('politics', 'topic_learning_history');

SELECT add_missing_timestamps('finance', 'rss_feeds');
SELECT add_missing_timestamps('finance', 'storyline_articles');
SELECT add_missing_timestamps('finance', 'topic_cluster_memberships');
SELECT add_missing_timestamps('finance', 'topic_clusters');
SELECT add_missing_timestamps('finance', 'topic_learning_history');

SELECT add_missing_timestamps('science_tech', 'rss_feeds');
SELECT add_missing_timestamps('science_tech', 'storyline_articles');
SELECT add_missing_timestamps('science_tech', 'topic_cluster_memberships');
SELECT add_missing_timestamps('science_tech', 'topic_clusters');
SELECT add_missing_timestamps('science_tech', 'topic_learning_history');

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    missing_count INTEGER;
BEGIN
    -- Count tables missing timestamps
    SELECT COUNT(*) INTO missing_count
    FROM (
        SELECT t.table_schema, t.table_name
        FROM information_schema.tables t
        WHERE t.table_schema IN ('politics', 'finance', 'science_tech')
        AND t.table_type = 'BASE TABLE'
        AND t.table_name IN ('rss_feeds', 'storyline_articles', 'topic_cluster_memberships', 
                            'topic_clusters', 'topic_learning_history')
        AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema = t.table_schema
            AND c.table_name = t.table_name
            AND c.column_name = 'created_at'
        )
    ) missing;
    
    IF missing_count > 0 THEN
        RAISE WARNING 'Still missing created_at on % tables', missing_count;
    ELSE
        RAISE NOTICE 'All tables now have created_at';
    END IF;
    
    SELECT COUNT(*) INTO missing_count
    FROM (
        SELECT t.table_schema, t.table_name
        FROM information_schema.tables t
        WHERE t.table_schema IN ('politics', 'finance', 'science_tech')
        AND t.table_type = 'BASE TABLE'
        AND t.table_name IN ('rss_feeds', 'storyline_articles', 'topic_cluster_memberships', 
                            'topic_clusters', 'topic_learning_history')
        AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema = t.table_schema
            AND c.table_name = t.table_name
            AND c.column_name = 'updated_at'
        )
    ) missing;
    
    IF missing_count > 0 THEN
        RAISE WARNING 'Still missing updated_at on % tables', missing_count;
    ELSE
        RAISE NOTICE 'All tables now have updated_at';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 124: Missing timestamp columns added';
END $$;

