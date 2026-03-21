-- Fix storyline trigger by adding missing created_by column
ALTER TABLE storylines 
ADD COLUMN IF NOT EXISTS created_by VARCHAR(255) DEFAULT 'system';

-- Update existing records to have created_by
UPDATE storylines 
SET created_by = COALESCE(created_by_user, 'system') 
WHERE created_by IS NULL OR created_by = 'system';

-- Also fix the trigger to use the correct column name
-- Drop the existing trigger
DROP TRIGGER IF EXISTS storyline_edit_trigger ON storylines;

-- Recreate the trigger with correct column reference
CREATE OR REPLACE FUNCTION log_storyline_edit()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO storyline_edit_log (storyline_id, edit_type, edit_description, edit_data, edited_by)
    VALUES (
        NEW.id,
        'storyline_updated',
        'Storyline updated: ' || COALESCE(NEW.title, 'Untitled'),
        jsonb_build_object(
            'title', NEW.title,
            'description', NEW.description,
            'status', NEW.processing_status,
            'master_summary', NEW.master_summary,
            'timeline_summary', NEW.timeline_summary
        ),
        COALESCE(NEW.created_by, 'system')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate the trigger
CREATE TRIGGER storyline_edit_trigger
    AFTER UPDATE ON storylines
    FOR EACH ROW
    EXECUTE FUNCTION log_storyline_edit();
