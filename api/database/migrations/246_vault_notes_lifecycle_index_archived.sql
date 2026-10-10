-- Allow vault note lifecycles for index (non-reading stubs) and archived junk.
ALTER TABLE intelligence.vault_notes
  DROP CONSTRAINT IF EXISTS vault_notes_lifecycle_check;

ALTER TABLE intelligence.vault_notes
  ADD CONSTRAINT vault_notes_lifecycle_check
  CHECK (
    lifecycle::text = ANY (
      ARRAY[
        'absent'::varchar,
        'stub'::varchar,
        'seeded'::varchar,
        'living'::varchar,
        'frozen'::varchar,
        'index'::varchar,
        'archived'::varchar
      ]::text[]
    )
  );
