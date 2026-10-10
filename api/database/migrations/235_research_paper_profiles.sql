-- Research-paper pathway: durable research axes separate from news claims/events.
CREATE TABLE IF NOT EXISTS intelligence.research_paper_profiles (
    id bigserial PRIMARY KEY,
    domain_key text NOT NULL,
    article_id integer NOT NULL,
    preprint_id text,
    doi text,
    arxiv_id text,
    research_question text,
    methods_summary text,
    findings_summary text,
    implications text,
    subjects_studied jsonb NOT NULL DEFAULT '[]'::jsonb,
    domain_facets jsonb NOT NULL DEFAULT '{}'::jsonb,
    raw_extraction jsonb NOT NULL DEFAULT '{}'::jsonb,
    extraction_status text NOT NULL DEFAULT 'pending',
    extraction_error text,
    extracted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT research_paper_profiles_domain_article_uq UNIQUE (domain_key, article_id),
    CONSTRAINT research_paper_profiles_status_chk CHECK (
        extraction_status IN ('pending', 'processing', 'done', 'failed', 'skipped')
    )
);

CREATE INDEX IF NOT EXISTS idx_research_paper_profiles_status_pending
    ON intelligence.research_paper_profiles (extraction_status, updated_at DESC)
    WHERE extraction_status IN ('pending', 'failed');

CREATE INDEX IF NOT EXISTS idx_research_paper_profiles_domain_extracted
    ON intelligence.research_paper_profiles (domain_key, extracted_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_research_paper_profiles_arxiv
    ON intelligence.research_paper_profiles (arxiv_id)
    WHERE arxiv_id IS NOT NULL;

COMMENT ON TABLE intelligence.research_paper_profiles IS
  'Scientific paper research axes (question/methods/findings/implications); not news entities/events.';
