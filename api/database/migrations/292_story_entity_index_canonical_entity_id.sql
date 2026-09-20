-- Migration 292: add nullable canonical_entity_id to per-domain story_entity_index.
-- Backfills by lower(entity_name) = lower(entity_canonical.canonical_name).
-- Idempotent.

DO $$
DECLARE
  sch TEXT;
BEGIN
  FOR sch IN
    SELECT DISTINCT table_schema
    FROM information_schema.tables
    WHERE table_name = 'story_entity_index'
      AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
  LOOP
    BEGIN
      EXECUTE format(
        'ALTER TABLE %I.story_entity_index
           ADD COLUMN IF NOT EXISTS canonical_entity_id INTEGER',
        sch
      );
      -- FK only if entity_canonical exists in the same schema
      IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = sch AND table_name = 'entity_canonical'
      ) THEN
        BEGIN
          EXECUTE format(
            'ALTER TABLE %I.story_entity_index
               DROP CONSTRAINT IF EXISTS story_entity_index_canonical_entity_id_fkey',
            sch
          );
          EXECUTE format(
            'ALTER TABLE %I.story_entity_index
               ADD CONSTRAINT story_entity_index_canonical_entity_id_fkey
               FOREIGN KEY (canonical_entity_id)
               REFERENCES %I.entity_canonical(id)
               ON DELETE SET NULL',
            sch,
            sch
          );
        EXCEPTION
          WHEN OTHERS THEN
            RAISE NOTICE '292: FK skip % — %', sch, SQLERRM;
        END;

        EXECUTE format(
          'CREATE INDEX IF NOT EXISTS idx_%s_sei_canonical
             ON %I.story_entity_index (canonical_entity_id)
             WHERE canonical_entity_id IS NOT NULL',
          sch,
          sch
        );

        EXECUTE format(
          $u$
          UPDATE %I.story_entity_index sei
          SET canonical_entity_id = ec.id
          FROM %I.entity_canonical ec
          WHERE sei.canonical_entity_id IS NULL
            AND lower(sei.entity_name) = lower(ec.canonical_name)
            AND (
              sei.entity_type = ec.entity_type
              OR sei.entity_type = 'other'
              OR ec.entity_type IS NULL
            )
          $u$,
          sch,
          sch
        );
      END IF;
    EXCEPTION
      WHEN OTHERS THEN
        RAISE NOTICE '292_story_entity_index_canonical: skip schema % — %', sch, SQLERRM;
    END;
  END LOOP;
END $$;
