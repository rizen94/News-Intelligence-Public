-- Migration 187: Medicine domain silo (schema medicine, public.domains row, table parity with science_tech).
-- Idempotent: safe to re-run with IF NOT EXISTS / ON CONFLICT DO NOTHING.
-- Prerequisites: create_domain_table, add_domain_foreign_keys, create_domain_indexes, create_domain_triggers (migration 122).

INSERT INTO public.domains (domain_key, name, schema_name, display_order, description)
VALUES (
    'medicine',
    'Medicine & Health Research',
    'medicine',
    20,
    'Medical research, clinical trials, epidemiology, public health, and biomedical advances.'
)
ON CONFLICT (domain_key) DO NOTHING;

INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)
SELECT d.id, 0, 0, 0, 0
FROM public.domains d
WHERE d.domain_key = 'medicine'
ON CONFLICT (domain_id) DO NOTHING;

CREATE SCHEMA IF NOT EXISTS medicine;

GRANT USAGE ON SCHEMA medicine TO newsapp;
GRANT CREATE ON SCHEMA medicine TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA medicine GRANT ALL ON TABLES TO newsapp;

SELECT public.create_domain_table('medicine', 'articles', 'science_tech');
SELECT public.create_domain_table('medicine', 'topics', 'science_tech');
SELECT public.create_domain_table('medicine', 'storylines', 'science_tech');
SELECT public.create_domain_table('medicine', 'rss_feeds', 'science_tech');
SELECT public.create_domain_table('medicine', 'article_topic_assignments', 'science_tech');
SELECT public.create_domain_table('medicine', 'storyline_articles', 'science_tech');
SELECT public.create_domain_table('medicine', 'topic_clusters', 'science_tech');
SELECT public.create_domain_table('medicine', 'topic_cluster_memberships', 'science_tech');
SELECT public.create_domain_table('medicine', 'topic_learning_history', 'science_tech');
SELECT public.create_domain_table('medicine', 'entity_canonical', 'science_tech');
SELECT public.create_domain_table('medicine', 'article_entities', 'science_tech');

SELECT public.add_domain_foreign_keys('medicine');
SELECT public.create_domain_indexes('medicine');
SELECT public.create_domain_triggers('medicine');

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'medicine' AND table_name = 'article_entities') THEN
    EXECUTE 'ALTER TABLE medicine.article_entities DROP CONSTRAINT IF EXISTS article_entities_article_id_fkey';
    EXECUTE 'ALTER TABLE medicine.article_entities ADD CONSTRAINT article_entities_article_id_fkey
      FOREIGN KEY (article_id) REFERENCES medicine.articles(id) ON DELETE CASCADE';
    EXECUTE 'ALTER TABLE medicine.article_entities DROP CONSTRAINT IF EXISTS article_entities_canonical_entity_id_fkey';
    EXECUTE 'ALTER TABLE medicine.article_entities ADD CONSTRAINT article_entities_canonical_entity_id_fkey
      FOREIGN KEY (canonical_entity_id) REFERENCES medicine.entity_canonical(id) ON DELETE SET NULL';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS medicine.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES medicine.storylines(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_medicine_sei_entity_name ON medicine.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_medicine_sei_storyline ON medicine.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_medicine_sei_core ON medicine.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_medicine_sei_entity_type ON medicine.story_entity_index (entity_type);
COMMENT ON TABLE medicine.story_entity_index IS 'v5: entity mentions per storyline for event→storyline matching (story_continuation)';

DO $$
BEGIN
  RAISE NOTICE 'Migration 187: medicine domain silo ensured (schema medicine, domains row, core tables)';
END $$;
