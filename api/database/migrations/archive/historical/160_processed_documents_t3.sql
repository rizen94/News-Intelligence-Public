-- Migration 160: T3.1 Document pipeline — processed_documents and document_intelligence
-- See docs/V6_QUALITY_FIRST_UPGRADE_PLAN.md section 4.4, V6_QUALITY_FIRST_TODO.md Tier 3.

-- Processed documents: metadata + URL; extracted content filled by T3.2 processing engine
CREATE TABLE IF NOT EXISTS intelligence.processed_documents (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50),
    source_name VARCHAR(255),
    source_url TEXT,
    title TEXT,
    publication_date DATE,
    authors TEXT[] DEFAULT '{}',
    document_type VARCHAR(50),
    extracted_sections JSONB DEFAULT '[]',
    key_findings JSONB DEFAULT '[]',
    entities_mentioned JSONB DEFAULT '[]',
    citations JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processed_documents_source_type ON intelligence.processed_documents(source_type);
CREATE INDEX IF NOT EXISTS idx_processed_documents_publication_date ON intelligence.processed_documents(publication_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_processed_documents_created ON intelligence.processed_documents(created_at DESC);

COMMENT ON TABLE intelligence.processed_documents IS 'T3.1: Ingested documents (metadata + URL); T3.2 populates extracted_sections, key_findings, entities_mentioned.';

-- Document intelligence: link documents to storylines and cross-document relations
CREATE TABLE IF NOT EXISTS intelligence.document_intelligence (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES intelligence.processed_documents(id) ON DELETE CASCADE,
    storyline_connections JSONB DEFAULT '[]',
    contradicts_document_ids INTEGER[] DEFAULT '{}',
    supports_document_ids INTEGER[] DEFAULT '{}',
    credibility_score DECIMAL(3,2),
    impact_assessment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_intelligence_document ON intelligence.document_intelligence(document_id);

COMMENT ON TABLE intelligence.document_intelligence IS 'T3.2: Links processed_documents to storylines; supports/contradicts for synthesis.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.processed_documents TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.document_intelligence TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.processed_documents_id_seq TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.document_intelligence_id_seq TO newsapp;
