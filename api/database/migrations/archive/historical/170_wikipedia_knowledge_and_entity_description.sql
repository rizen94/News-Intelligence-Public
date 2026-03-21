-- Migration 170: Entity Intelligence Overhaul — local Wikipedia knowledge base + entity_canonical description
-- See Entity Intelligence Overhaul plan: intelligence.wikipedia_knowledge table; entity_canonical.description, wikipedia_page_id

-- 1. Wikipedia knowledge table (intelligence schema)
CREATE TABLE IF NOT EXISTS intelligence.wikipedia_knowledge (
    id SERIAL PRIMARY KEY,
    page_id INTEGER UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    title_lower VARCHAR(500) NOT NULL,
    abstract TEXT NOT NULL,
    categories TEXT[] DEFAULT '{}',
    page_url VARCHAR(500),
    page_type VARCHAR(50),
    infobox JSONB DEFAULT '{}',
    aliases TEXT[] DEFAULT '{}',
    tsv tsvector,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_title_lower ON intelligence.wikipedia_knowledge (title_lower);
CREATE INDEX IF NOT EXISTS idx_wiki_tsv ON intelligence.wikipedia_knowledge USING GIN (tsv);
CREATE INDEX IF NOT EXISTS idx_wiki_aliases ON intelligence.wikipedia_knowledge USING GIN (aliases);
CREATE INDEX IF NOT EXISTS idx_wiki_page_type ON intelligence.wikipedia_knowledge (page_type);
CREATE INDEX IF NOT EXISTS idx_wiki_page_id ON intelligence.wikipedia_knowledge (page_id);

COMMENT ON TABLE intelligence.wikipedia_knowledge IS 'Local Wikipedia dump for entity background lookups; title_lower/tsv/aliases for search.';

-- Trigger to keep tsv in sync with title + abstract
CREATE OR REPLACE FUNCTION intelligence.wikipedia_knowledge_tsv_trigger() RETURNS trigger AS $$
BEGIN
    NEW.tsv := setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A')
        || setweight(to_tsvector('english', coalesce(NEW.abstract, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS wikipedia_knowledge_tsv_trigger ON intelligence.wikipedia_knowledge;
CREATE TRIGGER wikipedia_knowledge_tsv_trigger
    BEFORE INSERT OR UPDATE OF title, abstract ON intelligence.wikipedia_knowledge
    FOR EACH ROW EXECUTE PROCEDURE intelligence.wikipedia_knowledge_tsv_trigger();

-- Backfill tsv for any existing rows (no-op if empty)
UPDATE intelligence.wikipedia_knowledge SET tsv = setweight(to_tsvector('english', coalesce(title, '')), 'A') || setweight(to_tsvector('english', coalesce(abstract, '')), 'B') WHERE tsv IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.wikipedia_knowledge TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.wikipedia_knowledge_id_seq TO newsapp;

-- 2. Add description and wikipedia_page_id to entity_canonical (per domain)
DO $$
DECLARE
    s TEXT;
BEGIN
    FOREACH s IN ARRAY ARRAY['politics', 'finance', 'science_tech']
    LOOP
        EXECUTE format('ALTER TABLE %I.entity_canonical ADD COLUMN IF NOT EXISTS description TEXT', s);
        EXECUTE format('ALTER TABLE %I.entity_canonical ADD COLUMN IF NOT EXISTS wikipedia_page_id INTEGER', s);
        RAISE NOTICE 'Applied entity_canonical description columns to %.entity_canonical', s;
    END LOOP;
END $$;
