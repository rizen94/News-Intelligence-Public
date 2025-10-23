-- ============================================================================
-- ML PROCESSING ENHANCEMENT MIGRATION (Simplified)
-- ============================================================================
-- Adds enhanced ML processing tracking with queue position and timing
-- Migration: 050_ml_processing_enhancement_simple.sql
-- Date: $(date)
-- ============================================================================

-- Add new columns for enhanced ML processing tracking
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_last_processed TIMESTAMP;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_processing_duration INTEGER; -- in seconds
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_queue_position INTEGER DEFAULT 0;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_next_processing_estimate TIMESTAMP;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_processing_attempts INTEGER DEFAULT 0;
ALTER TABLE storylines ADD COLUMN IF NOT EXISTS ml_last_error TEXT;

-- Add comments for documentation
COMMENT ON COLUMN storylines.ml_last_processed IS 'Timestamp of last successful ML processing';
COMMENT ON COLUMN storylines.ml_processing_duration IS 'Duration of last ML processing in seconds';
COMMENT ON COLUMN storylines.ml_queue_position IS 'Current position in ML processing queue (0 = not queued)';
COMMENT ON COLUMN storylines.ml_next_processing_estimate IS 'Estimated time for next ML processing';
COMMENT ON COLUMN storylines.ml_processing_attempts IS 'Number of ML processing attempts';
COMMENT ON COLUMN storylines.ml_last_error IS 'Last ML processing error message';

-- Create index for queue position queries
CREATE INDEX IF NOT EXISTS idx_storylines_ml_queue ON storylines(ml_processing_status, ml_queue_position) 
WHERE ml_processing_status IN ('pending', 'queued');

-- Create index for processing timing queries
CREATE INDEX IF NOT EXISTS idx_storylines_ml_timing ON storylines(ml_last_processed, ml_next_processing_estimate);

-- Update existing storylines with default values
UPDATE storylines 
SET ml_queue_position = 0,
    ml_processing_attempts = 0,
    ml_last_processed = NULL,
    ml_processing_duration = NULL,
    ml_next_processing_estimate = NULL,
    ml_last_error = NULL
WHERE ml_queue_position IS NULL;

-- ============================================================================
-- ML PROCESSING QUEUE MANAGEMENT FUNCTIONS
-- ============================================================================

-- Function to get current ML processing queue
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
        s.id,
        s.title,
        s.ml_processing_status,
        s.ml_queue_position,
        s.article_count,
        s.last_article_added,
        s.created_at
    FROM storylines s
    WHERE s.ml_processing_status IN ('pending', 'queued')
    ORDER BY s.ml_queue_position ASC, s.last_article_added ASC;
END;
$$ LANGUAGE plpgsql;

-- Function to update queue positions
CREATE OR REPLACE FUNCTION update_ml_queue_positions()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER := 0;
    pos INTEGER := 1;
    storyline_record RECORD;
BEGIN
    -- Reset all queue positions
    UPDATE storylines SET ml_queue_position = 0 WHERE ml_processing_status NOT IN ('pending', 'queued');
    
    -- Update queue positions based on priority
    FOR storyline_record IN 
        SELECT id FROM storylines 
        WHERE ml_processing_status IN ('pending', 'queued')
        ORDER BY last_article_added ASC, created_at ASC
    LOOP
        UPDATE storylines 
        SET ml_queue_position = pos 
        WHERE id = storyline_record.id;
        pos := pos + 1;
        updated_count := updated_count + 1;
    END LOOP;
    
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- Function to estimate next processing time
CREATE OR REPLACE FUNCTION estimate_next_ml_processing()
RETURNS TIMESTAMP AS $$
DECLARE
    avg_duration INTEGER;
    queue_size INTEGER;
    currently_processing INTEGER;
    estimated_time TIMESTAMP;
BEGIN
    -- Get average processing duration
    SELECT COALESCE(AVG(ml_processing_duration), 300) INTO avg_duration 
    FROM storylines 
    WHERE ml_processing_duration IS NOT NULL;
    
    -- Get queue size
    SELECT COUNT(*) INTO queue_size 
    FROM storylines 
    WHERE ml_processing_status IN ('pending', 'queued');
    
    -- Get currently processing count
    SELECT COUNT(*) INTO currently_processing 
    FROM storylines 
    WHERE ml_processing_status = 'processing';
    
    -- Estimate time (assuming 1 ML worker)
    estimated_time := CURRENT_TIMESTAMP + INTERVAL '1 second' * (avg_duration * (queue_size + currently_processing));
    
    RETURN estimated_time;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
