-- Migration 254: Neurodiversity domain silo (schema neurodiversity, public.domains row, table parity with other domains).
-- Pairs with api/config/domains/neurodiversity.yaml (domain_key neurodiversity).
-- Idempotent: safe to re-run with IF NOT EXISTS / ON CONFLICT DO NOTHING.
-- Prerequisites: create_domain_table, add_domain_foreign_keys, create_domain_indexes, create_domain_triggers (migration 122).

INSERT INTO public.domains (domain_key, name, schema_name, display_order, description)
VALUES (
    'neurodiversity',
    'Neurodiversity (Autism / ADHD / AuDHD)',
    'neurodiversity',
    25,
    'Literature corpus for autism spectrum, ADHD, and overlapping AuDHD research — intake and evidence appraisal.'
)
ON CONFLICT (domain_key) DO NOTHING;

INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)
SELECT d.id, 0, 0, 0, 0
FROM public.domains d
WHERE d.domain_key = 'neurodiversity'
ON CONFLICT (domain_id) DO NOTHING;

CREATE SCHEMA IF NOT EXISTS neurodiversity;

GRANT USAGE ON SCHEMA neurodiversity TO newsapp;
GRANT CREATE ON SCHEMA neurodiversity TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA neurodiversity GRANT ALL ON TABLES TO newsapp;

SELECT public.create_domain_table('neurodiversity', 'articles', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'topics', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'storylines', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'rss_feeds', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'article_topic_assignments', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'storyline_articles', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'topic_clusters', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'topic_cluster_memberships', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'topic_learning_history', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'entity_canonical', 'science_tech');
SELECT public.create_domain_table('neurodiversity', 'article_entities', 'science_tech');

SELECT public.add_domain_foreign_keys('neurodiversity');

-- story_entity_index (same pattern as migration 180 legal)
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
CREATE INDEX IF NOT EXISTS idx_neurodiversity_sei_entity_name ON neurodiversity.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_neurodiversity_sei_storyline ON neurodiversity.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_neurodiversity_sei_core ON neurodiversity.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_neurodiversity_sei_entity_type ON neurodiversity.story_entity_index (entity_type);
COMMENT ON TABLE neurodiversity.story_entity_index IS 'v5: entity mentions per storyline for event→storyline matching';

-- article_entities FK fix-up (LIKE does not copy FKs to new schema)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'neurodiversity' AND table_name = 'article_entities') THEN
    EXECUTE 'ALTER TABLE neurodiversity.article_entities DROP CONSTRAINT IF EXISTS article_entities_article_id_fkey';
    EXECUTE 'ALTER TABLE neurodiversity.article_entities ADD CONSTRAINT article_entities_article_id_fkey
      FOREIGN KEY (article_id) REFERENCES neurodiversity.articles(id) ON DELETE CASCADE';
    EXECUTE 'ALTER TABLE neurodiversity.article_entities DROP CONSTRAINT IF EXISTS article_entities_canonical_entity_id_fkey';
    EXECUTE 'ALTER TABLE neurodiversity.article_entities ADD CONSTRAINT article_entities_canonical_entity_id_fkey
      FOREIGN KEY (canonical_entity_id) REFERENCES neurodiversity.entity_canonical(id) ON DELETE SET NULL';
  END IF;
END $$;

DO $$
BEGIN
  RAISE NOTICE 'Migration 254: neurodiversity domain silo ensured (schema neurodiversity, domains row, core tables)';
END $$;
