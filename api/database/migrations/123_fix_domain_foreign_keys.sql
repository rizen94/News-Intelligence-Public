-- Migration 123: Fix Missing Foreign Keys in Domain Schemas
-- Adds foreign key constraints to finance and science_tech schemas
-- Created: December 7, 2025
-- Version: 4.0.1

-- ============================================================================
-- FIX FOREIGN KEYS FOR FINANCE AND SCIENCE_TECH SCHEMAS
-- ============================================================================

-- Function to add foreign keys for a domain schema (recreate if needed)
CREATE OR REPLACE FUNCTION add_domain_foreign_keys(schema_name TEXT)
RETURNS VOID AS $$
BEGIN
    -- Article-Topic Assignments foreign keys
    EXECUTE format('
        -- Drop existing constraints if they exist
        ALTER TABLE %I.article_topic_assignments
        DROP CONSTRAINT IF EXISTS article_topic_assignments_article_id_fkey;
        
        ALTER TABLE %I.article_topic_assignments
        DROP CONSTRAINT IF EXISTS article_topic_assignments_topic_id_fkey;
        
        -- Add foreign keys
        ALTER TABLE %I.article_topic_assignments
        ADD CONSTRAINT article_topic_assignments_article_id_fkey
        FOREIGN KEY (article_id) REFERENCES %I.articles(id) ON DELETE CASCADE;
        
        ALTER TABLE %I.article_topic_assignments
        ADD CONSTRAINT article_topic_assignments_topic_id_fkey
        FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
    
    -- Storyline Articles foreign keys
    EXECUTE format('
        ALTER TABLE %I.storyline_articles
        DROP CONSTRAINT IF EXISTS storyline_articles_storyline_id_fkey;
        
        ALTER TABLE %I.storyline_articles
        DROP CONSTRAINT IF EXISTS storyline_articles_article_id_fkey;
        
        ALTER TABLE %I.storyline_articles
        ADD CONSTRAINT storyline_articles_storyline_id_fkey
        FOREIGN KEY (storyline_id) REFERENCES %I.storylines(id) ON DELETE CASCADE;
        
        ALTER TABLE %I.storyline_articles
        ADD CONSTRAINT storyline_articles_article_id_fkey
        FOREIGN KEY (article_id) REFERENCES %I.articles(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
    
    -- Topic Learning History foreign keys
    EXECUTE format('
        ALTER TABLE %I.topic_learning_history
        DROP CONSTRAINT IF EXISTS topic_learning_history_topic_id_fkey;
        
        ALTER TABLE %I.topic_learning_history
        ADD CONSTRAINT topic_learning_history_topic_id_fkey
        FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name);
    
    -- Topic Cluster Memberships foreign keys
    EXECUTE format('
        ALTER TABLE %I.topic_cluster_memberships
        DROP CONSTRAINT IF EXISTS topic_cluster_memberships_topic_id_fkey;
        
        ALTER TABLE %I.topic_cluster_memberships
        DROP CONSTRAINT IF EXISTS topic_cluster_memberships_cluster_id_fkey;
        
        ALTER TABLE %I.topic_cluster_memberships
        ADD CONSTRAINT topic_cluster_memberships_topic_id_fkey
        FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;
        
        ALTER TABLE %I.topic_cluster_memberships
        ADD CONSTRAINT topic_cluster_memberships_cluster_id_fkey
        FOREIGN KEY (cluster_id) REFERENCES %I.topic_clusters(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
END;
$$ LANGUAGE plpgsql;

-- Add foreign keys to finance schema
SELECT add_domain_foreign_keys('finance');

-- Add foreign keys to science_tech schema
SELECT add_domain_foreign_keys('science_tech');

-- Verify politics schema has all foreign keys (should already have them)
-- This is a no-op if they already exist
SELECT add_domain_foreign_keys('politics');

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    fk_count INTEGER;
BEGIN
    -- Count foreign keys in each schema
    FOR fk_count IN
        SELECT COUNT(*)
        FROM information_schema.table_constraints
        WHERE constraint_type = 'FOREIGN KEY'
        AND table_schema = 'politics'
        AND table_name IN ('article_topic_assignments', 'storyline_articles', 
                          'topic_learning_history', 'topic_cluster_memberships')
    LOOP
        RAISE NOTICE 'politics schema: % foreign keys', fk_count;
    END LOOP;
    
    FOR fk_count IN
        SELECT COUNT(*)
        FROM information_schema.table_constraints
        WHERE constraint_type = 'FOREIGN KEY'
        AND table_schema = 'finance'
        AND table_name IN ('article_topic_assignments', 'storyline_articles', 
                          'topic_learning_history', 'topic_cluster_memberships')
    LOOP
        RAISE NOTICE 'finance schema: % foreign keys', fk_count;
    END LOOP;
    
    FOR fk_count IN
        SELECT COUNT(*)
        FROM information_schema.table_constraints
        WHERE constraint_type = 'FOREIGN KEY'
        AND table_schema = 'science_tech'
        AND table_name IN ('article_topic_assignments', 'storyline_articles', 
                          'topic_learning_history', 'topic_cluster_memberships')
    LOOP
        RAISE NOTICE 'science_tech schema: % foreign keys', fk_count;
    END LOOP;
END $$;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 123: Foreign keys fixed for all domain schemas';
END $$;

