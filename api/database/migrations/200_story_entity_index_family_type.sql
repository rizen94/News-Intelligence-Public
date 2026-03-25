-- Add entity_type `family` to per-domain story_entity_index (aligns with article_entities / entity_canonical migration 199).

DO $$
DECLARE
  sch TEXT;
  r   RECORD;
BEGIN
  FOR sch IN
    SELECT DISTINCT table_schema
    FROM information_schema.tables
    WHERE table_name = 'story_entity_index'
      AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
  LOOP
    BEGIN
      FOR r IN
        SELECT c.conname AS cn
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = sch
          AND t.relname = 'story_entity_index'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) LIKE '%entity_type%'
      LOOP
        EXECUTE format('ALTER TABLE %I.story_entity_index DROP CONSTRAINT IF EXISTS %I', sch, r.cn);
      END LOOP;
      EXECUTE format(
        $f$
        ALTER TABLE %I.story_entity_index
          ADD CONSTRAINT story_entity_index_entity_type_check
          CHECK (entity_type IN (
            'person', 'organization', 'location', 'case_number',
            'legislation_id', 'event', 'other', 'family'
          ))
        $f$,
        sch
      );
    EXCEPTION
      WHEN OTHERS THEN
        RAISE NOTICE '200_story_entity_index_family_type: skip schema % — %', sch, SQLERRM;
    END;
  END LOOP;
END $$;
