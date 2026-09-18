-- Drop the two orphaned intelligence tables marked by migration 306.
--
-- SAFE TO LEAVE IN THE TREE. Without the explicit opt-in below it is a pure no-op: it raises a
-- NOTICE and returns, so a routine migration pass neither fails nor drops anything.
--
--   1. session var  ni.allow_orphan_table_drop = '1'  must be set (same opt-in shape as the
--      ni.membership_store_write guard in migration 298) — unset means skip;
--   2. once opted in, the table must contain ZERO rows;
--   3. once opted in, nothing may depend on it — no inbound foreign keys, no views, no matviews.
--
-- Conditions 2 and 3 raise and roll the whole migration back, leaving the tables and the
-- migration 306 comments in place. Deploy scripts apply migrations by explicit id only
-- (see the allowlist in scripts/deploy_to_widow.sh), so this never runs unattended.
--
-- Run the read-only checks in api/database/checks/orphan_table_drop_readiness.sql on Widow FIRST and
-- confirm they come back clean. See docs/ORPHANED_DB_SURFACES.md.
--
--   PGOPTIONS="-c ni.allow_orphan_table_drop=1" psql ... -f 307_drop_orphaned_intelligence_tables.sql
--
-- Evidence for orphanhood: no reader or writer in any tracked source, YAML, route, or script; the
-- only references are the creating migrations (261, 262). Audited 2026-09.

DO $$
DECLARE
    tbl TEXT;
    n_rows BIGINT;
    n_deps INT;
BEGIN
    IF COALESCE(current_setting('ni.allow_orphan_table_drop', true), '') <> '1' THEN
        -- No-op, not an error: a routine migration pass must never fail because of this file, and
        -- must never drop anything. Opt in explicitly once the readiness checks come back clean.
        RAISE NOTICE
            'Skipping orphan table drop: ni.allow_orphan_table_drop is not set. Run '
            'api/database/checks/orphan_table_drop_readiness.sql on Widow first, then re-run with '
            'PGOPTIONS="-c ni.allow_orphan_table_drop=1". See docs/ORPHANED_DB_SURFACES.md.';
        RETURN;
    END IF;

    FOR tbl IN SELECT unnest(ARRAY[
        'unseeded_claims_parking_lot',
        'entity_alias_merge_log'
    ])
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'intelligence' AND table_name = tbl
        ) THEN
            RAISE NOTICE 'intelligence.% already absent, skipping', tbl;
            CONTINUE;
        END IF;

        EXECUTE format('SELECT count(*) FROM intelligence.%I', tbl) INTO n_rows;
        IF n_rows <> 0 THEN
            RAISE EXCEPTION
                'intelligence.% holds % row(s); export or review before dropping (see '
                'docs/ORPHANED_DB_SURFACES.md)', tbl, n_rows;
        END IF;

        -- Inbound foreign keys from any other table.
        SELECT count(*) INTO n_deps
        FROM pg_constraint c
        JOIN pg_class ref ON ref.oid = c.confrelid
        JOIN pg_namespace refn ON refn.oid = ref.relnamespace
        WHERE c.contype = 'f' AND refn.nspname = 'intelligence' AND ref.relname = tbl;
        IF n_deps <> 0 THEN
            RAISE EXCEPTION 'intelligence.% is referenced by % foreign key(s)', tbl, n_deps;
        END IF;

        -- Views / matviews built on it.
        SELECT count(*) INTO n_deps
        FROM pg_depend d
        JOIN pg_rewrite r ON r.oid = d.objid
        JOIN pg_class v ON v.oid = r.ev_class
        JOIN pg_class t ON t.oid = d.refobjid
        JOIN pg_namespace tn ON tn.oid = t.relnamespace
        WHERE tn.nspname = 'intelligence'
          AND t.relname = tbl
          AND v.relkind IN ('v', 'm')
          AND v.relname <> tbl;
        IF n_deps <> 0 THEN
            RAISE EXCEPTION 'intelligence.% is used by % view(s)/matview(s)', tbl, n_deps;
        END IF;

        EXECUTE format('DROP TABLE intelligence.%I', tbl);
        RAISE NOTICE 'dropped intelligence.% (0 rows, no dependents)', tbl;
    END LOOP;
END $$;
