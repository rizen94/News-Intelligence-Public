-- Migration 209: Add context_text column to pattern matches
-- Adds the context_text column to support enhanced NLP pattern matching capabilities

ALTER TABLE intelligence.pattern_matches 
ADD COLUMN IF NOT EXISTS context_text TEXT;