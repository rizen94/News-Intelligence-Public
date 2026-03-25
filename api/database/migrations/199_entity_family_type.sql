-- Add entity_type `family` for surname umbrella entities (e.g. "Trump family") linking distinct persons.
-- Widens existing CHECK constraints on per-domain entity_canonical and article_entities.

DO $$
DECLARE
  sch TEXT;
  r   RECORD;
  has_ae BOOLEAN;
BEGIN
  FOR sch IN
    SELECT DISTINCT table_schema
    FROM information_schema.tables
    WHERE table_name = 'entity_canonical'
      AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
  LOOP
    BEGIN
      FOR r IN
        SELECT c.conname AS cn
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = sch
          AND t.relname = 'entity_canonical'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) LIKE '%entity_type%'
      LOOP
        EXECUTE format('ALTER TABLE %I.entity_canonical DROP CONSTRAINT IF EXISTS %I', sch, r.cn);
      END LOOP;
      EXECUTE format(
        $f$
        ALTER TABLE %I.entity_canonical
          ADD CONSTRAINT entity_canonical_entity_type_check
          CHECK (entity_type IN (
            'person', 'organization', 'subject', 'recurring_event', 'family'
          ))
        $f$,
        sch
      );

      SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = sch AND table_name = 'article_entities'
      ) INTO has_ae;
      IF has_ae THEN
        FOR r IN
          SELECT c.conname AS cn
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace
          WHERE n.nspname = sch
            AND t.relname = 'article_entities'
            AND c.contype = 'c'
            AND pg_get_constraintdef(c.oid) LIKE '%entity_type%'
        LOOP
          EXECUTE format('ALTER TABLE %I.article_entities DROP CONSTRAINT IF EXISTS %I', sch, r.cn);
        END LOOP;
        EXECUTE format(
          $f$
          ALTER TABLE %I.article_entities
            ADD CONSTRAINT article_entities_entity_type_check
            CHECK (entity_type IN (
              'person', 'organization', 'subject', 'recurring_event', 'family'
            ))
          $f$,
          sch
        );
      END IF;
    EXCEPTION
      WHEN OTHERS THEN
        RAISE NOTICE '199_entity_family_type: skip schema % — %', sch, SQLERRM;
    END;
  END LOOP;
END $$;
