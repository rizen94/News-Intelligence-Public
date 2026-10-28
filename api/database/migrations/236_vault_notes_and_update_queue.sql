-- Migration 236: Two-level vault notes registry + update queue
-- Postgres owns structure pointers / lifecycle; Obsidian vault owns longform prose.

CREATE SCHEMA IF NOT EXISTS intelligence;

-- Registry: structured pointer from NI objects → vault markdown path
CREATE TABLE IF NOT EXISTS intelligence.vault_notes (
    id BIGSERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    note_type VARCHAR(32) NOT NULL
        CHECK (note_type IN ('entity', 'connection', 'event', 'storyline')),
    object_id INTEGER NOT NULL,
    object_id_secondary INTEGER,
    vault_path TEXT NOT NULL,
    note_status VARCHAR(32) NOT NULL DEFAULT 'absent'
        CHECK (note_status IN (
            'absent', 'stub', 'seeded', 'living', 'frozen',
            'structure_only', 'note_pending', 'note_ready'
        )),
    lifecycle VARCHAR(32) NOT NULL DEFAULT 'stub'
        CHECK (lifecycle IN ('absent', 'stub', 'seeded', 'living', 'frozen')),
    title TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    mention_count INTEGER NOT NULL DEFAULT 0,
    alias_ids INTEGER[] NOT NULL DEFAULT '{}',
    last_article_id INTEGER,
    sources_last_scan_at TIMESTAMPTZ,
    note_updated_at TIMESTAMPTZ,
    rag_indexed_at TIMESTAMPTZ,
    rag_fingerprint TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (vault_path)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vault_notes_object_unique
    ON intelligence.vault_notes (
        domain_key,
        note_type,
        object_id,
        COALESCE(object_id_secondary, 0)
    );

CREATE INDEX IF NOT EXISTS idx_vault_notes_domain_type_status
    ON intelligence.vault_notes (domain_key, note_type, note_status);

CREATE INDEX IF NOT EXISTS idx_vault_notes_lifecycle
    ON intelligence.vault_notes (lifecycle)
    WHERE lifecycle IN ('stub', 'seeded', 'living');

COMMENT ON TABLE intelligence.vault_notes IS
    'Two-level knowledge: structured registry mapping entities/events/connections to Obsidian vault paths.';

-- Work queue for unattended vault create/update
CREATE TABLE IF NOT EXISTS intelligence.vault_update_queue (
    id BIGSERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    note_type VARCHAR(32) NOT NULL
        CHECK (note_type IN ('entity', 'connection', 'event', 'storyline')),
    object_id INTEGER NOT NULL,
    object_id_secondary INTEGER,
    vault_path TEXT NOT NULL,
    action VARCHAR(16) NOT NULL DEFAULT 'update'
        CHECK (action IN ('create', 'update', 'seed', 'significance')),
    priority VARCHAR(16) NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('high', 'medium', 'low')),
    status VARCHAR(32) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead')),
    idempotency_key TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    locked_by TEXT,
    locked_until TIMESTAMPTZ,
    error_message TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vault_update_idempotency
    ON intelligence.vault_update_queue (idempotency_key);

CREATE INDEX IF NOT EXISTS idx_vault_update_pending
    ON intelligence.vault_update_queue (status, priority, created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_vault_update_path_lock
    ON intelligence.vault_update_queue (vault_path, status);

COMMENT ON TABLE intelligence.vault_update_queue IS
    'Unattended vault notetaking jobs: claim/lease per vault_path, idempotent create/update.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.vault_notes TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.vault_notes_id_seq TO newsapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.vault_update_queue TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.vault_update_queue_id_seq TO newsapp;
