-- Migration 239: Reader home feed indexes
-- Speeds LATERAL aggregates on storyline_articles and merged_into_id filters.

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT d.schema_name FROM public.domains d WHERE d.is_active = true
    LOOP
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%I_sa_storyline_added_at ON %I.storyline_articles (storyline_id, added_at DESC NULLS LAST)',
            schema_name,
            schema_name
        );
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%I_storylines_unmerged_updated ON %I.storylines (updated_at DESC NULLS LAST) WHERE merged_into_id IS NULL',
            schema_name,
            schema_name
        );
    END LOOP;
    RAISE NOTICE 'Migration 239: reader home indexes ensured for active domain schemas';
END $$;

-- tracked_events.storyline_id and domain_keys GIN already exist (see prior migrations).
