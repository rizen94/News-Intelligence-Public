-- Migration 244: expansion + daily_briefing note types; mirror longform body in PG

ALTER TABLE intelligence.vault_notes
    DROP CONSTRAINT IF EXISTS vault_notes_note_type_check;

ALTER TABLE intelligence.vault_notes
    ADD CONSTRAINT vault_notes_note_type_check
    CHECK (note_type IN (
        'entity', 'connection', 'event', 'storyline', 'cluster', 'clipping',
        'expansion', 'daily_briefing'
    ));

ALTER TABLE intelligence.vault_update_queue
    DROP CONSTRAINT IF EXISTS vault_update_queue_note_type_check;

ALTER TABLE intelligence.vault_update_queue
    ADD CONSTRAINT vault_update_queue_note_type_check
    CHECK (note_type IN (
        'entity', 'connection', 'event', 'storyline', 'cluster', 'clipping',
        'expansion', 'daily_briefing'
    ));

ALTER TABLE intelligence.vault_notes
    ADD COLUMN IF NOT EXISTS body_md TEXT,
    ADD COLUMN IF NOT EXISTS summary_md TEXT;

COMMENT ON COLUMN intelligence.vault_notes.body_md IS
    'Mirrored Obsidian longform (expansions, daily briefings) for fast reader indexing.';
COMMENT ON COLUMN intelligence.vault_notes.summary_md IS
    'Short dek / lead excerpt mirrored from body for home cards.';
COMMENT ON COLUMN intelligence.vault_notes.note_type IS
    'entity|connection|event|storyline|cluster|clipping|expansion|daily_briefing';

CREATE INDEX IF NOT EXISTS idx_vault_notes_expansion_article
    ON intelligence.vault_notes ((metadata->>'source_article_id'))
    WHERE note_type = 'expansion';

CREATE INDEX IF NOT EXISTS idx_vault_notes_daily_briefing_day
    ON intelligence.vault_notes (domain_key, object_id DESC)
    WHERE note_type = 'daily_briefing';
