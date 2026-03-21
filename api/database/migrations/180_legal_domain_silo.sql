-- Migration 180: Legal domain silo (schema legal, public.domains row, table parity with science_tech).
-- Idempotent: safe to re-run with IF NOT EXISTS / ON CONFLICT DO NOTHING.
-- Prerequisites: create_domain_table, add_domain_foreign_keys, create_domain_indexes, create_domain_triggers (migration 122).

INSERT INTO public.domains (domain_key, name, schema_name, display_order, description)
VALUES (
    'legal',
    'Legal',
    'legal',
    4,
    'Court decisions, legislation, regulatory enforcement, and legal industry news.'
)
ON CONFLICT (domain_key) DO NOTHING;

INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)
SELECT d.id, 0, 0, 0, 0
FROM public.domains d
WHERE d.domain_key = 'legal'
ON CONFLICT (domain_id) DO NOTHING;

CREATE SCHEMA IF NOT EXISTS legal;

GRANT USAGE ON SCHEMA legal TO newsapp;
GRANT CREATE ON SCHEMA legal TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA legal GRANT ALL ON TABLES TO newsapp;

-- Clone core silo from science_tech (current shape includes migrations through 179-era columns).
SELECT public.create_domain_table('legal', 'articles', 'science_tech');
SELECT public.create_domain_table('legal', 'topics', 'science_tech');
SELECT public.create_domain_table('legal', 'storylines', 'science_tech');
SELECT public.create_domain_table('legal', 'rss_feeds', 'science_tech');
SELECT public.create_domain_table('legal', 'article_topic_assignments', 'science_tech');
SELECT public.create_domain_table('legal', 'storyline_articles', 'science_tech');
SELECT public.create_domain_table('legal', 'topic_clusters', 'science_tech');
SELECT public.create_domain_table('legal', 'topic_cluster_memberships', 'science_tech');
SELECT public.create_domain_table('legal', 'topic_learning_history', 'science_tech');
SELECT public.create_domain_table('legal', 'entity_canonical', 'science_tech');
SELECT public.create_domain_table('legal', 'article_entities', 'science_tech');

SELECT public.add_domain_foreign_keys('legal');
SELECT public.create_domain_indexes('legal');
SELECT public.create_domain_triggers('legal');

-- Foreign keys for entity tables (LIKE does not copy FKs to legal.articles / legal.entity_canonical).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'legal' AND table_name = 'article_entities') THEN
    EXECUTE 'ALTER TABLE legal.article_entities DROP CONSTRAINT IF EXISTS article_entities_article_id_fkey';
    EXECUTE 'ALTER TABLE legal.article_entities ADD CONSTRAINT article_entities_article_id_fkey
      FOREIGN KEY (article_id) REFERENCES legal.articles(id) ON DELETE CASCADE';
    EXECUTE 'ALTER TABLE legal.article_entities DROP CONSTRAINT IF EXISTS article_entities_canonical_entity_id_fkey';
    EXECUTE 'ALTER TABLE legal.article_entities ADD CONSTRAINT article_entities_canonical_entity_id_fkey
      FOREIGN KEY (canonical_entity_id) REFERENCES legal.entity_canonical(id) ON DELETE SET NULL';
  END IF;
END $$;

-- story_entity_index (same as migration 179 pattern)
CREATE TABLE IF NOT EXISTS legal.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES legal.storylines(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_legal_sei_entity_name ON legal.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_legal_sei_storyline ON legal.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_legal_sei_core ON legal.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_legal_sei_entity_type ON legal.story_entity_index (entity_type);
COMMENT ON TABLE legal.story_entity_index IS 'v5: entity mentions per storyline for event→storyline matching (story_continuation)';

DO $$
BEGIN
  RAISE NOTICE 'Migration 180: legal domain silo ensured (schema legal, domains row, core tables)';
END $$;
