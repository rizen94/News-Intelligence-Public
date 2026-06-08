-- Migration 229: Entity extraction auxiliary tables for legal/medicine/artificial_intelligence.
-- politics has article_extracted_* / article_keywords; newer silos were missing them,
-- causing entity extraction transactions to abort after article_entities insert.

DO $$
DECLARE
    sch text;
    tbl text;
BEGIN
    FOREACH sch IN ARRAY ARRAY['legal', 'medicine', 'artificial_intelligence'] LOOP
        FOREACH tbl IN ARRAY ARRAY[
            'article_extracted_dates',
            'article_extracted_times',
            'article_extracted_countries',
            'article_keywords'
        ] LOOP
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = sch AND table_name = tbl
            ) THEN
                CONTINUE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'politics' AND table_name = tbl
            ) THEN
                RAISE NOTICE 'politics.% missing — skip clone for %.%', tbl, sch, tbl;
                CONTINUE;
            END IF;
            EXECUTE format(
                'CREATE TABLE %I.%I (LIKE politics.%I INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)',
                sch,
                tbl,
                tbl
            );
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
