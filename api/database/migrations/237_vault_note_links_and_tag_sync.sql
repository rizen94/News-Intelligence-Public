-- Migration 237: Obsidian tag/link mirror + location structure on vault_notes
-- Obsidian remains SSOT for relational tags/wikilinks; Postgres mirrors for packs.

ALTER TABLE intelligence.vault_notes
    ADD COLUMN IF NOT EXISTS tags_source VARCHAR(32) NOT NULL DEFAULT 'obsidian'
        CHECK (tags_source IN ('obsidian', 'ni_structural', 'merged')),
    ADD COLUMN IF NOT EXISTS tags_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS links_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS geo_parent_entity_id INTEGER,
    ADD COLUMN IF NOT EXISTS place_kind VARCHAR(64);

COMMENT ON COLUMN intelligence.vault_notes.tags IS
    'Mirror of Obsidian frontmatter tags; Obsidian wins on sync.';
COMMENT ON COLUMN intelligence.vault_notes.tags_source IS
    'Who last authored the mirrored tag list (obsidian preferred).';
COMMENT ON COLUMN intelligence.vault_notes.geo_parent_entity_id IS
    'Hard place hierarchy (e.g. Hormuz → Iran). Not for soft relations.';
COMMENT ON COLUMN intelligence.vault_notes.place_kind IS
    'place/chokepoint|country|city|region — structural only.';

CREATE INDEX IF NOT EXISTS idx_vault_notes_geo_parent
    ON intelligence.vault_notes (geo_parent_entity_id)
    WHERE geo_parent_entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vault_notes_tags_gin
    ON intelligence.vault_notes USING GIN (tags);

CREATE TABLE IF NOT EXISTS intelligence.vault_note_links (
    id BIGSERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    src_vault_path TEXT NOT NULL,
    dst_vault_path TEXT,
    dst_title TEXT NOT NULL,
    link_kind VARCHAR(32) NOT NULL DEFAULT 'wikilink'
        CHECK (link_kind IN ('wikilink', 'tag_ref')),
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (src_vault_path, dst_title, link_kind)
);

CREATE INDEX IF NOT EXISTS idx_vault_note_links_src
    ON intelligence.vault_note_links (src_vault_path);

CREATE INDEX IF NOT EXISTS idx_vault_note_links_dst_path
    ON intelligence.vault_note_links (dst_vault_path)
    WHERE dst_vault_path IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vault_note_links_domain
    ON intelligence.vault_note_links (domain_key, link_kind);

COMMENT ON TABLE intelligence.vault_note_links IS
    'Cache of Obsidian wikilinks/tag refs. Obsidian is SSOT; rebuilt on vault sync.';

GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence.vault_note_links TO newsapp;
GRANT USAGE, SELECT ON SEQUENCE intelligence.vault_note_links_id_seq TO newsapp;
