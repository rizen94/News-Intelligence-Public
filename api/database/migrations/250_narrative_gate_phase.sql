-- 250_narrative_gate_phase.sql
-- Add narrative_gate_phase column to all domain storylines tables.
-- This column tracks where each storyline sits in the narrative processing
-- lifecycle, enabling phased narrow-debt-drain filtering.

DO $$
DECLARE
    s text;
    rec record;
BEGIN
    FOR rec IN SELECT table_schema FROM information_schema.tables
               WHERE table_name = 'storylines' AND table_type = 'BASE TABLE'
                 AND table_schema NOT IN ('pg_catalog', 'information_schema')
    LOOP
        s := format(
            'ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS narrative_gate_phase VARCHAR(60) DEFAULT ''storyline_processing''::varchar',
            rec.table_schema
        );
        EXECUTE s;

        -- Migrate existing narrow_debt_pending status from narrative_finisher_meta
        -- into the new column so drain works on pre-existing debt without a migration pass.
        s := format(
            $u$UPDATE %I.storylines SET narrative_gate_phase = 'narrow_debt_pending'::varchar
              WHERE narrative_finisher_meta IS NOT NULL
                AND (narrative_finisher_meta->>'narrow_debt_pending') IN ('true', 't', '1')$u$,
            rec.table_schema
        );
        EXECUTE s;

        -- Default any remaining NULL rows to the initial processing phase.
        s := format(
            $u$UPDATE %I.storylines SET narrative_gate_phase = 'storyline_processing'::varchar
              WHERE narrative_gate_phase IS NULL$u$,
            rec.table_schema
        );
        EXECUTE s;
    END LOOP;
END $$;
