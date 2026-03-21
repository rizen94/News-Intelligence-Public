-- Migration 182: add_domain_foreign_keys — skip optional topic tables when absent
-- Fixes legal silo (180) when template schema never had topic_learning_history /
-- topic_cluster_memberships (create_domain_table skips missing sources).

CREATE OR REPLACE FUNCTION add_domain_foreign_keys(schema_name TEXT)
RETURNS VOID AS $$
BEGIN
    EXECUTE format('
        ALTER TABLE %I.article_topic_assignments
        DROP CONSTRAINT IF EXISTS article_topic_assignments_article_id_fkey;

        ALTER TABLE %I.article_topic_assignments
        ADD CONSTRAINT article_topic_assignments_article_id_fkey
        FOREIGN KEY (article_id) REFERENCES %I.articles(id) ON DELETE CASCADE;

        ALTER TABLE %I.article_topic_assignments
        DROP CONSTRAINT IF EXISTS article_topic_assignments_topic_id_fkey;

        ALTER TABLE %I.article_topic_assignments
        ADD CONSTRAINT article_topic_assignments_topic_id_fkey
        FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);

    EXECUTE format('
        ALTER TABLE %I.storyline_articles
        DROP CONSTRAINT IF EXISTS storyline_articles_storyline_id_fkey;

        ALTER TABLE %I.storyline_articles
        ADD CONSTRAINT storyline_articles_storyline_id_fkey
        FOREIGN KEY (storyline_id) REFERENCES %I.storylines(id) ON DELETE CASCADE;

        ALTER TABLE %I.storyline_articles
        DROP CONSTRAINT IF EXISTS storyline_articles_article_id_fkey;

        ALTER TABLE %I.storyline_articles
        ADD CONSTRAINT storyline_articles_article_id_fkey
        FOREIGN KEY (article_id) REFERENCES %I.articles(id) ON DELETE CASCADE;
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);

    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = schema_name
          AND table_name = 'topic_learning_history'
    ) THEN
        EXECUTE format('
            ALTER TABLE %I.topic_learning_history
            DROP CONSTRAINT IF EXISTS topic_learning_history_topic_id_fkey;

            ALTER TABLE %I.topic_learning_history
            ADD CONSTRAINT topic_learning_history_topic_id_fkey
            FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;
        ', schema_name, schema_name, schema_name);
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = schema_name
          AND table_name = 'topic_cluster_memberships'
    ) THEN
        EXECUTE format('
            ALTER TABLE %I.topic_cluster_memberships
            DROP CONSTRAINT IF EXISTS topic_cluster_memberships_topic_id_fkey;

            ALTER TABLE %I.topic_cluster_memberships
            ADD CONSTRAINT topic_cluster_memberships_topic_id_fkey
            FOREIGN KEY (topic_id) REFERENCES %I.topics(id) ON DELETE CASCADE;

            ALTER TABLE %I.topic_cluster_memberships
            DROP CONSTRAINT IF EXISTS topic_cluster_memberships_cluster_id_fkey;

            ALTER TABLE %I.topic_cluster_memberships
            ADD CONSTRAINT topic_cluster_memberships_cluster_id_fkey
            FOREIGN KEY (cluster_id) REFERENCES %I.topic_clusters(id) ON DELETE CASCADE;
        ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION add_domain_foreign_keys(TEXT) IS
    'Adds intra-domain FKs; optional topic_learning_history / topic_cluster_memberships only if tables exist (182).';
