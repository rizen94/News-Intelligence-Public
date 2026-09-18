-- Migration 247: Restore SERIAL id defaults on article_topic_clusters for all pipeline silos.
-- politics_2 / finance_2 were omitted from 228; cloned tables lack nextval() on id,
-- breaking topic_clustering INSERT (null id).

DO $$
DECLARE
    sch text;
BEGIN
    FOR sch IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname IN (
            'legal',
            'medicine',
            'artificial_intelligence',
            'politics_2',
            'finance_2'
        )
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = sch AND table_name = 'article_topic_clusters'
        ) THEN
            CONTINUE;
        END IF;

        EXECUTE format(
            'CREATE SEQUENCE IF NOT EXISTS %I.article_topic_clusters_id_seq',
            sch
        );

        EXECUTE format(
            'SELECT setval(%L, COALESCE((SELECT MAX(id) FROM %I.article_topic_clusters), 0) + 1, false)',
            sch || '.article_topic_clusters_id_seq',
            sch
        );

        EXECUTE format(
            'ALTER TABLE %I.article_topic_clusters ALTER COLUMN id SET DEFAULT nextval(%L)',
            sch,
            sch || '.article_topic_clusters_id_seq'
        );

        EXECUTE format(
            'ALTER SEQUENCE %I.article_topic_clusters_id_seq OWNED BY %I.article_topic_clusters.id',
            sch,
            sch
        );
    END LOOP;
END $$;

-- politics_2 / finance_2 may be absent on hosts that never cloned those silos.
