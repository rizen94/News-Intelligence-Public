-- Migration 291: align neurodiversity.story_entity_index entity_type CHECK with
-- migration 200 (include 'family'). Idempotent — safe if already applied.

DO $$
DECLARE
  r RECORD;
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'neurodiversity'
      AND table_name = 'story_entity_index'
  ) THEN
    RAISE NOTICE '291: neurodiversity.story_entity_index missing — skip';
    RETURN;
  END IF;

  FOR r IN
    SELECT c.conname AS cn
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'neurodiversity'
      AND t.relname = 'story_entity_index'
      AND c.contype = 'c'
      AND pg_get_constraintdef(c.oid) LIKE '%entity_type%'
  LOOP
    EXECUTE format(
      'ALTER TABLE neurodiversity.story_entity_index DROP CONSTRAINT IF EXISTS %I',
      r.cn
    );
  END LOOP;

  ALTER TABLE neurodiversity.story_entity_index
    ADD CONSTRAINT story_entity_index_entity_type_check
    CHECK (entity_type IN (
      'person', 'organization', 'location', 'case_number',
      'legislation_id', 'event', 'other', 'family'
    ));
END $$;
