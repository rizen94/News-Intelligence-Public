-- v12 membership SSOT: optional write-freeze on storyline_articles (bag table).
-- Inserts allowed only when session var ni.membership_store_write = '1'
-- (set by shared.membership_store during dual-write / legacy paths).

DO $$
DECLARE
    sch TEXT;
BEGIN
    FOR sch IN SELECT unnest(ARRAY[
        'politics', 'finance', 'medicine', 'legal',
        'artificial_intelligence', 'environment', 'environment_climate', 'neurodiversity'
    ])
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = sch AND table_name = 'storyline_articles'
        ) THEN
            EXECUTE format($t$
                CREATE OR REPLACE FUNCTION %I.storyline_articles_write_guard()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $fn$
                BEGIN
                    IF COALESCE(current_setting('ni.membership_store_write', true), '') <> '1' THEN
                        RAISE EXCEPTION
                            'storyline_articles write-frozen: use membership_store.admit (schema=%%)',
                            TG_TABLE_SCHEMA;
                    END IF;
                    RETURN NEW;
                END;
                $fn$;
            $t$, sch);

            EXECUTE format(
                'DROP TRIGGER IF EXISTS trg_storyline_articles_write_guard ON %I.storyline_articles',
                sch
            );
            EXECUTE format(
                'CREATE TRIGGER trg_storyline_articles_write_guard
                 BEFORE INSERT ON %I.storyline_articles
                 FOR EACH ROW EXECUTE FUNCTION %I.storyline_articles_write_guard()',
                sch,
                sch
            );
        END IF;
    END LOOP;
END $$;
