-- Migration 283: Neurodiversity domain silo (corpus processing_mode).
-- Autism / ADHD / AuDHD literature intake + evidence appraisal only.
-- Idempotent. Apply on local news_intel_dev first; do NOT apply on Widow until v11 cutover.
-- Prerequisites: migration 282 (processing_mode), create_domain_table helpers, medicine schema.

INSERT INTO public.domains (domain_key, name, schema_name, display_order, description, is_active, processing_mode)
VALUES (
    'neurodiversity',
    'Neurodiversity (Autism / ADHD / AuDHD)',
    'neurodiversity',
    25,
    'Literature corpus for autism spectrum, ADHD, and overlapping AuDHD — intake and evidence appraisal only.',
    true,
    'corpus'
)
ON CONFLICT (domain_key) DO UPDATE
SET
    name = EXCLUDED.name,
    schema_name = EXCLUDED.schema_name,
    display_order = EXCLUDED.display_order,
    description = EXCLUDED.description,
    processing_mode = EXCLUDED.processing_mode;

INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)
SELECT d.id, 0, 0, 0, 0
FROM public.domains d
WHERE d.domain_key = 'neurodiversity'
ON CONFLICT (domain_id) DO NOTHING;

CREATE SCHEMA IF NOT EXISTS neurodiversity;

GRANT USAGE ON SCHEMA neurodiversity TO newsapp;
GRANT CREATE ON SCHEMA neurodiversity TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA neurodiversity GRANT ALL ON TABLES TO newsapp;

-- Clone core tables from medicine (science_tech retired).
SELECT public.create_domain_table('neurodiversity', 'articles', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'topics', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'storylines', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'rss_feeds', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'article_topic_assignments', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'storyline_articles', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'topic_clusters', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'topic_cluster_memberships', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'topic_learning_history', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'entity_canonical', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'article_entities', 'medicine');
SELECT public.create_domain_table('neurodiversity', 'article_topic_clusters', 'medicine');

SELECT public.add_domain_foreign_keys('neurodiversity');
SELECT public.create_domain_indexes('neurodiversity');
SELECT public.create_domain_triggers('neurodiversity');

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'neurodiversity' AND table_name = 'article_entities'
  ) THEN
    EXECUTE 'ALTER TABLE neurodiversity.article_entities DROP CONSTRAINT IF EXISTS article_entities_article_id_fkey';
    EXECUTE 'ALTER TABLE neurodiversity.article_entities ADD CONSTRAINT article_entities_article_id_fkey
      FOREIGN KEY (article_id) REFERENCES neurodiversity.articles(id) ON DELETE CASCADE';
    EXECUTE 'ALTER TABLE neurodiversity.article_entities DROP CONSTRAINT IF EXISTS article_entities_canonical_entity_id_fkey';
    EXECUTE 'ALTER TABLE neurodiversity.article_entities ADD CONSTRAINT article_entities_canonical_entity_id_fkey
      FOREIGN KEY (canonical_entity_id) REFERENCES neurodiversity.entity_canonical(id) ON DELETE SET NULL';
  END IF;
END $$;

-- Publication identity for literature dedup across PubMed / Europe PMC / preprints / CT.gov
ALTER TABLE neurodiversity.articles ADD COLUMN IF NOT EXISTS doi TEXT;
ALTER TABLE neurodiversity.articles ADD COLUMN IF NOT EXISTS pmid TEXT;
ALTER TABLE neurodiversity.articles ADD COLUMN IF NOT EXISTS pmcid TEXT;
ALTER TABLE neurodiversity.articles ADD COLUMN IF NOT EXISTS nct_id TEXT;
ALTER TABLE neurodiversity.articles ADD COLUMN IF NOT EXISTS abstract_only BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS ux_neurodiversity_articles_doi
    ON neurodiversity.articles (lower(doi)) WHERE doi IS NOT NULL AND btrim(doi) <> '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_neurodiversity_articles_pmid
    ON neurodiversity.articles (pmid) WHERE pmid IS NOT NULL AND btrim(pmid) <> '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_neurodiversity_articles_pmcid
    ON neurodiversity.articles (pmcid) WHERE pmcid IS NOT NULL AND btrim(pmcid) <> '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_neurodiversity_articles_nct_id
    ON neurodiversity.articles (nct_id) WHERE nct_id IS NOT NULL AND btrim(nct_id) <> '';

COMMENT ON COLUMN neurodiversity.articles.doi IS 'Crossref/DOI identity for literature dedup';
COMMENT ON COLUMN neurodiversity.articles.pmid IS 'PubMed PMID';
COMMENT ON COLUMN neurodiversity.articles.pmcid IS 'PubMed Central PMCID';
COMMENT ON COLUMN neurodiversity.articles.nct_id IS 'ClinicalTrials.gov NCT id';
COMMENT ON COLUMN neurodiversity.articles.abstract_only IS
  'True when full text unavailable; abstract-only rows cannot receive evidence_grade=strong';

CREATE TABLE IF NOT EXISTS neurodiversity.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES neurodiversity.storylines(id) ON DELETE CASCADE,
    entity_name VARCHAR(255) NOT NULL,
    entity_role VARCHAR(100),
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
        'person', 'organization', 'location', 'case_number',
        'legislation_id', 'event', 'other'
    )),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    mention_count INTEGER DEFAULT 1,
    is_core_entity BOOLEAN DEFAULT FALSE,
    UNIQUE (storyline_id, entity_name, entity_type)
);
CREATE INDEX IF NOT EXISTS idx_neurodiversity_sei_entity_name
    ON neurodiversity.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_neurodiversity_sei_storyline
    ON neurodiversity.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_neurodiversity_sei_core
    ON neurodiversity.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;

DO $$
BEGIN
  RAISE NOTICE 'Migration 283: neurodiversity corpus silo ensured (processing_mode=corpus, publication identity cols)';
END $$;
