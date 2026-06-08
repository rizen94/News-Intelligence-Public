-- Migration 228: Restore SERIAL id defaults on legal/medicine/artificial_intelligence entity tables.
-- Cloned silos were missing sequences on entity_canonical and article_entities (and article_topic_clusters),
-- causing entity extraction INSERT failures (null id).

DO $$
DECLARE
    sch text;
    tbl text;
BEGIN
    FOREACH sch IN ARRAY ARRAY['legal', 'medicine', 'artificial_intelligence'] LOOP
        FOREACH tbl IN ARRAY ARRAY['entity_canonical', 'article_entities', 'article_topic_clusters'] LOOP
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = sch AND table_name = tbl
            ) THEN
                CONTINUE;
            END IF;

            EXECUTE format(
                'CREATE SEQUENCE IF NOT EXISTS %I.%I_id_seq',
                sch,
                tbl
            );

            EXECUTE format(
                'SELECT setval(%L, COALESCE((SELECT MAX(id) FROM %I.%I), 0) + 1, false)',
                sch || '.' || tbl || '_id_seq',
                sch,
                tbl
            );

            EXECUTE format(
                'ALTER TABLE %I.%I ALTER COLUMN id SET DEFAULT nextval(%L)',
                sch,
                tbl,
                sch || '.' || tbl || '_id_seq'
            );

            EXECUTE format(
                'ALTER SEQUENCE %I.%I_id_seq OWNED BY %I.%I.id',
                sch,
                tbl,
                sch,
                tbl
            );
        END LOOP;
    END LOOP;
END $$;

COMMENT ON SCHEMA legal IS 'Migration 228: entity table id sequences restored for extraction pipeline';
