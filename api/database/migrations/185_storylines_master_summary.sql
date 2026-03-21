-- Migration 185: ML / storyline master summary column on domain storylines
-- Code paths (storyline CRUD, automation storyline_processing, backlog_metrics) expect
-- politics/finance/science_tech.storylines.master_summary (TEXT, nullable).

DO $$
DECLARE
    s text;
BEGIN
    FOREACH s IN ARRAY ARRAY['politics', 'finance', 'science_tech']
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS master_summary TEXT',
            s
        );
        EXECUTE format(
            'COMMENT ON COLUMN %I.storylines.master_summary IS %L',
            s,
            'Narrative summary from ML pipeline; UI/API also use analysis_summary.'
        );
    END LOOP;

    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'legal'
          AND table_name = 'storylines'
    ) THEN
        ALTER TABLE legal.storylines
            ADD COLUMN IF NOT EXISTS master_summary TEXT;
        COMMENT ON COLUMN legal.storylines.master_summary IS
            'Narrative summary from ML pipeline; UI/API also use analysis_summary.';
    END IF;
END $$;
