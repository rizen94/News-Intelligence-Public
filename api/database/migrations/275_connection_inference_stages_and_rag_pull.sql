-- Migration 275: Chemistry-style connection inference stages + RAG evidence pull queue
-- Loose → candidate → established (plus hypothesized for random collisions).

ALTER TABLE intelligence.graph_connection_proposals
    ADD COLUMN IF NOT EXISTS inference_stage TEXT NOT NULL DEFAULT 'candidate';

ALTER TABLE intelligence.graph_connection_proposals
    DROP CONSTRAINT IF EXISTS graph_connection_proposals_inference_stage_check;

ALTER TABLE intelligence.graph_connection_proposals
    ADD CONSTRAINT graph_connection_proposals_inference_stage_check
    CHECK (inference_stage IN (
        'hypothesized',
        'candidate',
        'established',
        'quarantined'
    ));

COMMENT ON COLUMN intelligence.graph_connection_proposals.inference_stage IS
    'Chemistry model: hypothesized (random/weak) → candidate (stimuli) → established (protein) | quarantined';

CREATE INDEX IF NOT EXISTS idx_graph_connection_proposals_inference_stage
    ON intelligence.graph_connection_proposals (inference_stage, status, confidence DESC);

-- Optional stage on materialized links
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'intelligence' AND table_name = 'graph_connection_links'
    ) THEN
        ALTER TABLE intelligence.graph_connection_links
            ADD COLUMN IF NOT EXISTS inference_stage TEXT NOT NULL DEFAULT 'established';
    END IF;
END $$;

-- Selective RAG / evidence pull tickets (arXiv PDF, extra chunks) triggered by thin bonds
CREATE TABLE IF NOT EXISTS intelligence.rag_evidence_pull_queue (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    domain_key TEXT NOT NULL DEFAULT 'artificial-intelligence',
    article_id BIGINT,
    arxiv_id TEXT,
    pdf_url TEXT,
    proposal_id BIGINT,
    storyline_id BIGINT,
    interest_score DOUBLE PRECISION,
    selection_reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending_approval'
        CHECK (status IN (
            'pending_approval',
            'queued',
            'downloading',
            'processing',
            'complete',
            'rejected',
            'failed'
        )),
    processed_document_id BIGINT,
    agent_notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolved_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_evidence_pull_article
    ON intelligence.rag_evidence_pull_queue (domain_key, article_id)
    WHERE article_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_evidence_pull_arxiv
    ON intelligence.rag_evidence_pull_queue (arxiv_id)
    WHERE arxiv_id IS NOT NULL AND arxiv_id <> '';

CREATE INDEX IF NOT EXISTS idx_rag_evidence_pull_status
    ON intelligence.rag_evidence_pull_queue (status, created_at DESC);

COMMENT ON TABLE intelligence.rag_evidence_pull_queue IS
    'Selective RAG stimulus: pull fuller source (e.g. arXiv PDF) when a loose connection needs evidence.';
