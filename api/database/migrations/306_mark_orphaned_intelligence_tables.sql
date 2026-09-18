-- Mark two orphaned intelligence tables. Non-destructive: comments only, no DDL on data.
--
-- Neither table is read or written by any tracked source, YAML, route, or script. The only
-- references anywhere are the migrations that created them (261, 262). Found by matching every
-- migration CREATE TABLE against the live tree during the 2026-09 waste review; see
-- docs/ORPHANED_DB_SURFACES.md before dropping either one.
--
-- intelligence.unseeded_claims_parking_lot (261) — do not confuse with the *editorial* parking lot
-- that api/scripts/triage_editorial_parking_lot.py operates on; that is a different table.
-- intelligence.entity_alias_merge_log (262) — alias merge hygiene audit trail that nothing writes.
--
-- Dropping needs a row-count check on Widow first, so this migration deliberately only labels them.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'intelligence' AND table_name = 'unseeded_claims_parking_lot'
    ) THEN
        COMMENT ON TABLE intelligence.unseeded_claims_parking_lot IS
            'ORPHANED (audited 2026-09): no reader or writer in the tree. Created by migration 261. '
            'Not the editorial parking lot used by triage_editorial_parking_lot.py. '
            'See docs/ORPHANED_DB_SURFACES.md.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'intelligence' AND table_name = 'entity_alias_merge_log'
    ) THEN
        COMMENT ON TABLE intelligence.entity_alias_merge_log IS
            'ORPHANED (audited 2026-09): no reader or writer in the tree. Created by migration 262. '
            'See docs/ORPHANED_DB_SURFACES.md.';
    END IF;
END $$;
