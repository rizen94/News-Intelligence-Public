-- Migration 201: Template-style silos politics-2 / finance-2 (schemas politics_2, finance_2).
-- Parallel to legacy politics / finance for gradual data migration. Idempotent.
-- Clone core tables from science_tech; story_entity_index CHECK includes ``family`` (post-200 shape).

-- ---------- politics-2 ----------
INSERT INTO public.domains (domain_key, name, schema_name, display_order, description)
VALUES (
    'politics-2',
    'Politics (template)',
    'politics_2',
    25,
    'YAML-onboarded politics silo; ingest target while legacy politics schema is phased out.'
)
ON CONFLICT (domain_key) DO NOTHING;

INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)
SELECT d.id, 0, 0, 0, 0
FROM public.domains d
WHERE d.domain_key = 'politics-2'
ON CONFLICT (domain_id) DO NOTHING;

CREATE SCHEMA IF NOT EXISTS politics_2;

GRANT USAGE ON SCHEMA politics_2 TO newsapp;
GRANT CREATE ON SCHEMA politics_2 TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA politics_2 GRANT ALL ON TABLES TO newsapp;

SELECT public.create_domain_table('politics_2', 'articles', 'science_tech');
SELECT public.create_domain_table('politics_2', 'topics', 'science_tech');
SELECT public.create_domain_table('politics_2', 'storylines', 'science_tech');
SELECT public.create_domain_table('politics_2', 'rss_feeds', 'science_tech');
SELECT public.create_domain_table('politics_2', 'article_topic_assignments', 'science_tech');
SELECT public.create_domain_table('politics_2', 'storyline_articles', 'science_tech');
SELECT public.create_domain_table('politics_2', 'topic_clusters', 'science_tech');
SELECT public.create_domain_table('politics_2', 'topic_cluster_memberships', 'science_tech');
SELECT public.create_domain_table('politics_2', 'topic_learning_history', 'science_tech');
SELECT public.create_domain_table('politics_2', 'entity_canonical', 'science_tech');
SELECT public.create_domain_table('politics_2', 'article_entities', 'science_tech');

SELECT public.add_domain_foreign_keys('politics_2');
SELECT public.create_domain_indexes('politics_2');
SELECT public.create_domain_triggers('politics_2');

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'politics_2' AND table_name = 'article_entities') THEN
    EXECUTE 'ALTER TABLE politics_2.article_entities DROP CONSTRAINT IF EXISTS article_entities_article_id_fkey';
    EXECUTE 'ALTER TABLE politics_2.article_entities ADD CONSTRAINT article_entities_article_id_fkey
      FOREIGN KEY (article_id) REFERENCES politics_2.articles(id) ON DELETE CASCADE';
    EXECUTE 'ALTER TABLE politics_2.article_entities DROP CONSTRAINT IF EXISTS article_entities_canonical_entity_id_fkey';
    EXECUTE 'ALTER TABLE politics_2.article_entities ADD CONSTRAINT article_entities_canonical_entity_id_fkey
      FOREIGN KEY (canonical_entity_id) REFERENCES politics_2.entity_canonical(id) ON DELETE SET NULL';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS politics_2.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES politics_2.storylines(id) ON DELETE CASCADE,
    entity_name VARCHAR(255) NOT NULL,
    entity_role VARCHAR(100),
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
        'person', 'organization', 'location', 'case_number',
        'legislation_id', 'event', 'other', 'family'
    )),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    mention_count INTEGER DEFAULT 1,
    is_core_entity BOOLEAN DEFAULT FALSE,
    UNIQUE (storyline_id, entity_name, entity_type)
);
CREATE INDEX IF NOT EXISTS idx_politics_2_sei_entity_name ON politics_2.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_politics_2_sei_storyline ON politics_2.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_politics_2_sei_core ON politics_2.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_politics_2_sei_entity_type ON politics_2.story_entity_index (entity_type);
COMMENT ON TABLE politics_2.story_entity_index IS 'v5: entity mentions per storyline (politics-2 template silo)';

-- ---------- finance-2 ----------
INSERT INTO public.domains (domain_key, name, schema_name, display_order, description)
VALUES (
    'finance-2',
    'Finance (template)',
    'finance_2',
    26,
    'YAML-onboarded finance silo; ingest target while legacy finance schema is phased out.'
)
ON CONFLICT (domain_key) DO NOTHING;

INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)
SELECT d.id, 0, 0, 0, 0
FROM public.domains d
WHERE d.domain_key = 'finance-2'
ON CONFLICT (domain_id) DO NOTHING;

CREATE SCHEMA IF NOT EXISTS finance_2;

GRANT USAGE ON SCHEMA finance_2 TO newsapp;
GRANT CREATE ON SCHEMA finance_2 TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA finance_2 GRANT ALL ON TABLES TO newsapp;

SELECT public.create_domain_table('finance_2', 'articles', 'science_tech');
SELECT public.create_domain_table('finance_2', 'topics', 'science_tech');
SELECT public.create_domain_table('finance_2', 'storylines', 'science_tech');
SELECT public.create_domain_table('finance_2', 'rss_feeds', 'science_tech');
SELECT public.create_domain_table('finance_2', 'article_topic_assignments', 'science_tech');
SELECT public.create_domain_table('finance_2', 'storyline_articles', 'science_tech');
SELECT public.create_domain_table('finance_2', 'topic_clusters', 'science_tech');
SELECT public.create_domain_table('finance_2', 'topic_cluster_memberships', 'science_tech');
SELECT public.create_domain_table('finance_2', 'topic_learning_history', 'science_tech');
SELECT public.create_domain_table('finance_2', 'entity_canonical', 'science_tech');
SELECT public.create_domain_table('finance_2', 'article_entities', 'science_tech');

SELECT public.add_domain_foreign_keys('finance_2');
SELECT public.create_domain_indexes('finance_2');
SELECT public.create_domain_triggers('finance_2');

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'finance_2' AND table_name = 'article_entities') THEN
    EXECUTE 'ALTER TABLE finance_2.article_entities DROP CONSTRAINT IF EXISTS article_entities_article_id_fkey';
    EXECUTE 'ALTER TABLE finance_2.article_entities ADD CONSTRAINT article_entities_article_id_fkey
      FOREIGN KEY (article_id) REFERENCES finance_2.articles(id) ON DELETE CASCADE';
    EXECUTE 'ALTER TABLE finance_2.article_entities DROP CONSTRAINT IF EXISTS article_entities_canonical_entity_id_fkey';
    EXECUTE 'ALTER TABLE finance_2.article_entities ADD CONSTRAINT article_entities_canonical_entity_id_fkey
      FOREIGN KEY (canonical_entity_id) REFERENCES finance_2.entity_canonical(id) ON DELETE SET NULL';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS finance_2.story_entity_index (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES finance_2.storylines(id) ON DELETE CASCADE,
    entity_name VARCHAR(255) NOT NULL,
    entity_role VARCHAR(100),
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
        'person', 'organization', 'location', 'case_number',
        'legislation_id', 'event', 'other', 'family'
    )),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    mention_count INTEGER DEFAULT 1,
    is_core_entity BOOLEAN DEFAULT FALSE,
    UNIQUE (storyline_id, entity_name, entity_type)
);
CREATE INDEX IF NOT EXISTS idx_finance_2_sei_entity_name ON finance_2.story_entity_index (LOWER(entity_name));
CREATE INDEX IF NOT EXISTS idx_finance_2_sei_storyline ON finance_2.story_entity_index (storyline_id);
CREATE INDEX IF NOT EXISTS idx_finance_2_sei_core ON finance_2.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;
CREATE INDEX IF NOT EXISTS idx_finance_2_sei_entity_type ON finance_2.story_entity_index (entity_type);
COMMENT ON TABLE finance_2.story_entity_index IS 'v5: entity mentions per storyline (finance-2 template silo)';

DO $$
BEGIN
  RAISE NOTICE 'Migration 201: politics_2 + finance_2 silos ensured';
END $$;
