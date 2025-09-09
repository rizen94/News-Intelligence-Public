-- RAG Context Storage for Storylines
-- Migration 010: Add RAG context support

-- Create storyline RAG context table
CREATE TABLE IF NOT EXISTS storyline_rag_context (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL UNIQUE,
    rag_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_storyline_rag_context_storyline_id 
ON storyline_rag_context (storyline_id);

CREATE INDEX IF NOT EXISTS idx_storyline_rag_context_updated_at 
ON storyline_rag_context (updated_at DESC);

-- Add RAG context summary to storylines table
ALTER TABLE storylines 
ADD COLUMN IF NOT EXISTS rag_context_summary TEXT,
ADD COLUMN IF NOT EXISTS rag_enhanced_at TIMESTAMP WITH TIME ZONE;

-- Create index for RAG enhanced storylines
CREATE INDEX IF NOT EXISTS idx_storylines_rag_enhanced_at 
ON storylines (rag_enhanced_at DESC);

-- Add RAG context to storyline articles for tracking
ALTER TABLE storyline_articles 
ADD COLUMN IF NOT EXISTS rag_enhanced BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS rag_enhanced_at TIMESTAMP WITH TIME ZONE;

-- Create index for RAG enhanced articles
CREATE INDEX IF NOT EXISTS idx_storyline_articles_rag_enhanced 
ON storyline_articles (rag_enhanced, rag_enhanced_at DESC);



