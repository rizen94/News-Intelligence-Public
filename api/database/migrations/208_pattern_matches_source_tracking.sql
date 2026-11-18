-- Migration 208: Add source tracking to pattern matches
-- Adds the source_ids_used column to support pattern matching with source tracking
-- Also adds context_text column for enhanced NLP capabilities

ALTER TABLE intelligence.pattern_matches 
ADD COLUMN IF NOT EXISTS source_ids_used TEXT[],
ADD COLUMN IF NOT EXISTS context_text TEXT;