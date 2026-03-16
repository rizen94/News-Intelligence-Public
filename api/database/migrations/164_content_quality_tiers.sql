-- Migration 164: Content quality tiers and clickbait/sensationalism metrics.
-- Adds quality_tier, quality_scores JSONB, clickbait_probability, fact_density,
-- source_reliability, quality_flags to articles per domain. Creates content_quality_metrics.
-- See docs/CONTENT_QUALITY_STANDARDS.md.

-- Per-domain articles: add quality tier and sub-scores (IF NOT EXISTS for idempotency)
DO $$
DECLARE
    s TEXT;
BEGIN
    FOREACH s IN ARRAY ARRAY['politics', 'finance', 'science_tech']
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS quality_tier SMALLINT DEFAULT 3 CHECK (quality_tier >= 1 AND quality_tier <= 4)',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS quality_scores JSONB DEFAULT ''{}''',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS clickbait_probability DECIMAL(3,2) DEFAULT NULL',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS fact_density DECIMAL(3,2) DEFAULT NULL',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS source_reliability DECIMAL(3,2) DEFAULT NULL',
            s
        );
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS quality_flags TEXT[] DEFAULT ''{}''',
            s
        );
    END LOOP;
END $$;

-- Indexes for quality filtering (briefings, storylines)
CREATE INDEX IF NOT EXISTS idx_politics_articles_quality_tier ON politics.articles(quality_tier) WHERE quality_tier IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_finance_articles_quality_tier ON finance.articles(quality_tier) WHERE quality_tier IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_science_tech_articles_quality_tier ON science_tech.articles(quality_tier) WHERE quality_tier IS NOT NULL;

-- Optional: aggregate metrics by source for monitoring and source reputation
CREATE TABLE IF NOT EXISTS public.content_quality_metrics (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50) NOT NULL,
    source_domain VARCHAR(255) NOT NULL,
    avg_quality_score DECIMAL(3,2),
    clickbait_rate DECIMAL(3,2),
    fact_density_avg DECIMAL(3,2),
    article_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, source_domain)
);

CREATE INDEX IF NOT EXISTS idx_content_quality_metrics_domain ON public.content_quality_metrics(domain);
CREATE INDEX IF NOT EXISTS idx_content_quality_metrics_source ON public.content_quality_metrics(source_domain);
CREATE INDEX IF NOT EXISTS idx_content_quality_metrics_updated ON public.content_quality_metrics(last_updated);

COMMENT ON TABLE public.content_quality_metrics IS 'Per-source quality aggregates for monitoring and source reputation';
