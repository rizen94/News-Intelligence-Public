-- ============================================================================
-- FIX ML QUEUE FUNCTION DATA TYPES
-- ============================================================================
-- Fixes data type mismatch in get_ml_processing_queue function
-- Migration: 051_fix_ml_queue_function.sql
-- ============================================================================

-- Drop and recreate the function with correct data types
DROP FUNCTION IF EXISTS get_ml_processing_queue();

CREATE OR REPLACE FUNCTION get_ml_processing_queue()
RETURNS TABLE (
    storyline_id VARCHAR,
    title VARCHAR,
    ml_processing_status VARCHAR,
    ml_queue_position INTEGER,
    article_count INTEGER,
    last_article_added TIMESTAMP,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id::VARCHAR,
        s.title::VARCHAR,
        s.ml_processing_status::VARCHAR,
        s.ml_queue_position,
        s.article_count,
        s.last_article_added,
        s.created_at
    FROM storylines s
    WHERE s.ml_processing_status IN ('pending', 'queued')
    ORDER BY s.ml_queue_position ASC, s.last_article_added ASC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
