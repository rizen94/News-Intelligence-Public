-- Add created_by column to storylines table
ALTER TABLE storylines 
ADD COLUMN IF NOT EXISTS created_by VARCHAR(50) DEFAULT 'user';

-- Add index for created_by column
CREATE INDEX IF NOT EXISTS idx_storylines_created_by 
ON storylines (created_by);
