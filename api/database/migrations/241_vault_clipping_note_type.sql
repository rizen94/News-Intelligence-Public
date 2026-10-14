-- Migration 241: vault clipping note_type (second-brain raw/source layer)

ALTER TABLE intelligence.vault_notes
    DROP CONSTRAINT IF EXISTS vault_notes_note_type_check;

ALTER TABLE intelligence.vault_notes
    ADD CONSTRAINT vault_notes_note_type_check
    CHECK (note_type IN ('entity', 'connection', 'event', 'storyline', 'cluster', 'clipping'));

ALTER TABLE intelligence.vault_update_queue
    DROP CONSTRAINT IF EXISTS vault_update_queue_note_type_check;

ALTER TABLE intelligence.vault_update_queue
    ADD CONSTRAINT vault_update_queue_note_type_check
    CHECK (note_type IN ('entity', 'connection', 'event', 'storyline', 'cluster', 'clipping'));

CREATE INDEX IF NOT EXISTS idx_vault_notes_clipping_article
    ON intelligence.vault_notes ((metadata->>'article_id'))
    WHERE note_type = 'clipping' OR (metadata->>'clipping') = 'true';

COMMENT ON COLUMN intelligence.vault_notes.note_type IS
    'entity|connection|event|storyline|cluster|clipping — clipping = second-brain raw source capture';
