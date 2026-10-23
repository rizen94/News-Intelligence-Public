-- Migration 240: vault cluster hub note_type + hub lookup indexes
-- First-class Obsidian cluster hubs (index only — no storyline membership merge).

ALTER TABLE intelligence.vault_notes
    DROP CONSTRAINT IF EXISTS vault_notes_note_type_check;

ALTER TABLE intelligence.vault_notes
    ADD CONSTRAINT vault_notes_note_type_check
    CHECK (note_type IN ('entity', 'connection', 'event', 'storyline', 'cluster'));

ALTER TABLE intelligence.vault_update_queue
    DROP CONSTRAINT IF EXISTS vault_update_queue_note_type_check;

ALTER TABLE intelligence.vault_update_queue
    ADD CONSTRAINT vault_update_queue_note_type_check
    CHECK (note_type IN ('entity', 'connection', 'event', 'storyline', 'cluster'));

CREATE INDEX IF NOT EXISTS idx_vault_notes_hub_meta
    ON intelligence.vault_notes ((metadata->>'hub'))
    WHERE note_type = 'cluster'
       OR (metadata->>'hub') = 'true';

CREATE INDEX IF NOT EXISTS idx_vault_notes_cluster_key
    ON intelligence.vault_notes ((metadata->>'cluster_key'))
    WHERE metadata ? 'cluster_key';

COMMENT ON COLUMN intelligence.vault_notes.note_type IS
    'entity|connection|event|storyline|cluster — cluster = Obsidian hub index (no bag membership)';
