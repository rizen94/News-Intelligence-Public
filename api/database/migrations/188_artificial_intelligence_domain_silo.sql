-- Migration 188: Artificial Intelligence domain silo (schema artificial_intelligence, public.domains row, table parity with science_tech).
-- Pairs with api/config/domains/artificial-intelligence.yaml (domain_key artificial-intelligence).
-- Idempotent: safe to re-run with IF NOT EXISTS / ON CONFLICT DO NOTHING.
-- Prerequisites: create_domain_table, add_domain_foreign_keys, create_domain_indexes, create_domain_triggers (migration 122).

INSERT INTO public.domains (domain_key, name, schema_name, display_order, description)
VALUES (
    'artificial-intelligence',
    'Artificial Intelligence & Machine Learning',
    'artificial_intelligence',
    25,
    'AI research breakthroughs, model comparisons, practical applications, enterprise adoption, and emerging AI careers. Covers LLMs, computer vision, robotics, and AI governance.'
)
ON CONFLICT (domain_key) DO NOTHING;

INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)
SELECT d.id, 0, 0, 0, 0
FROM public.domains d
WHERE d.domain_key = 'artificial-intelligence'
ON CONFLICT (domain_id) DO NOTHING;

CREATE SCHEMA IF NOT EXISTS artificial_intelligence;

GRANT USAGE ON SCHEMA artificial_intelligence TO newsapp;
GRANT CREATE ON SCHEMA artificial_intelligence TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA artificial_intelligence GRANT ALL ON TABLES TO newsapp;

SELECT public.create_domain_table('artificial_intelligence', 'articles', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'topics', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'storylines', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'rss_feeds', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'article_topic_assignments', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'storyline_articles', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'topic_clusters', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'topic_cluster_memberships', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'topic_learning_history', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'entity_canonical', 'science_tech');
SELECT public.create_domain_table('artificial_intelligence', 'article_entities', 'science_tech');

SELECT public.add_domain_foreign_keys('artificial_intelligence');
SELECT public.create_domain_indexes('artificial_intelligence');
SELECT public.create_domain_triggers('artificial_intelligence');

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'artificial_intelligence' AND table_name = 'article_entities'
  ) THEN
    EXECUTE 'ALTER TABLE artificial_intelligence.article_entities DROP CONSTRAINT IF EXISTS article_entities_article_id_fkey';
    EXECUTE 'ALTER TABLE artificial_intelligence.article_entities ADD CONSTRAINT article_entities_article_id_fkey
      FOREIGN KEY (article_id) REFERENCES artificial_intelligence.articles(id) ON DELETE CASCADE';
    EXECUTE 'ALTER TABLE artificial_intelligence.article_entities DROP CONSTRAINT IF EXISTS article_entities_canonical_entity_id_fkey';
    EXECUTE 'ALTER TABLE artificial_intelligence.article_entities ADD CONSTRAINT article_entities_canonical_entity_id_fkey
      FOREIGN KEY (canonical_entity_id) REFERENCES artificial_intelligence.entity_canonical(id) ON DELETE SET NULL';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS artificial_intelligence.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES artificial_intelligence.storylines(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_artificial_intelligence_sei_entity_name ON artificial_intelligence.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_artificial_intelligence_sei_storyline ON artificial_intelligence.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_artificial_intelligence_sei_core ON artificial_intelligence.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_artificial_intelligence_sei_entity_type ON artificial_intelligence.story_entity_index (entity_type);
COMMENT ON TABLE artificial_intelligence.story_entity_index IS 'v5: entity mentions per storyline for event→storyline matching (story_continuation)';

DO $$
BEGIN
  RAISE NOTICE 'Migration 188: artificial_intelligence domain silo ensured (schema artificial_intelligence, domains row, core tables)';
END $$;
