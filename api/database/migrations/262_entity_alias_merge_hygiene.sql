-- Create table to track entity alias merges for hygiene/auditing
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'intelligence' AND table_name = 'entity_alias_merge_log') THEN
        CREATE TABLE intelligence.entity_alias_merge_log (
            id SERIAL PRIMARY KEY,
            canonical_entity_id INTEGER NOT NULL,
            alias_entity_id INTEGER NOT NULL,
            alias_name TEXT NOT NULL,
            merge_reason TEXT,
            merged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            merged_by TEXT DEFAULT 'system',
            CONSTRAINT fk_canonical_entity FOREIGN KEY (canonical_entity_id) REFERENCES intelligence.entity_profiles(id),
            CONSTRAINT fk_alias_entity FOREIGN KEY (alias_entity_id) REFERENCES intelligence.entity_profiles(id),
            UNIQUE(canonical_entity_id, alias_entity_id)
        );
    END IF;
END $$;

-- Create indexes for performance
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'intelligence' AND tablename = 'entity_alias_merge_log' AND indexname = 'idx_entity_alias_merge_canonical') THEN
        CREATE INDEX idx_entity_alias_merge_canonical ON intelligence.entity_alias_merge_log (canonical_entity_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'intelligence' AND tablename = 'entity_alias_merge_log' AND indexname = 'idx_entity_alias_merge_alias') THEN
        CREATE INDEX idx_entity_alias_merge_alias ON intelligence.entity_alias_merge_log (alias_entity_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'intelligence' AND tablename = 'entity_alias_merge_log' AND indexname = 'idx_entity_alias_merge_merged_at') THEN
        CREATE INDEX idx_entity_alias_merge_merged_at ON intelligence.entity_alias_merge_log (merged_at);
    END IF;
END $$;