-- Migration 231: storylines.updated_at only on material changes (not RAG/review/automation metadata).
-- Replaces blind update_updated_at_column() triggers on domain storylines tables.

BEGIN;

CREATE OR REPLACE FUNCTION public.update_storylines_updated_at_material_only()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
  END IF;
  IF (
    OLD.title IS DISTINCT FROM NEW.title
    OR OLD.description IS DISTINCT FROM NEW.description
    OR OLD.status IS DISTINCT FROM NEW.status
    OR OLD.article_count IS DISTINCT FROM NEW.article_count
    OR OLD.merged_into_id IS DISTINCT FROM NEW.merged_into_id
  ) THEN
    NEW.updated_at = CURRENT_TIMESTAMP;
  ELSIF NEW.updated_at IS DISTINCT FROM OLD.updated_at THEN
    -- Honor explicit updated_at (article link backfill, manual correction)
    NULL;
  ELSE
    NEW.updated_at = OLD.updated_at;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  tr RECORD;
BEGIN
  FOR tr IN
    SELECT t.tgname AS tgname, n.nspname AS nspname, c.relname AS relname
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = 'storylines'
      AND NOT t.tgisinternal
      AND pg_get_triggerdef(t.oid) LIKE '%update_updated_at_column%'
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', tr.tgname, tr.nspname, tr.relname);
    EXECUTE format(
      'CREATE TRIGGER %I BEFORE UPDATE ON %I.%I FOR EACH ROW EXECUTE FUNCTION public.update_storylines_updated_at_material_only()',
      tr.tgname, tr.nspname, tr.relname
    );
  END LOOP;
END $$;

-- Align historical updated_at with last linked article (review passes inflated updated_at).
DO $$
DECLARE
  r RECORD;
  stmt TEXT;
BEGIN
  FOR r IN
    SELECT DISTINCT schema_name
    FROM public.domains
    WHERE schema_name IS NOT NULL AND schema_name <> ''
  LOOP
    stmt := format(
      $sql$
      UPDATE %I.storylines s
      SET updated_at = COALESCE(
        (SELECT MAX(sa.added_at) FROM %I.storyline_articles sa WHERE sa.storyline_id = s.id),
        s.created_at
      )
      WHERE s.merged_into_id IS NULL;
      $sql$,
      r.schema_name,
      r.schema_name
    );
    EXECUTE stmt;
  END LOOP;
END $$;

COMMIT;
