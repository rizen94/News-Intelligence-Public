-- Post-unification bake: drop stale nri.* tables after cutover to intelligence.investigation_*.
-- Preconditions: USE_INVESTIGATION_PREFIXED_TABLES=true; row counts verified on investigation_* tables.
-- Homelab postgres-mcp prompts updated to query intelligence.investigation_* (not nri.*).

BEGIN;

DROP SCHEMA IF EXISTS nri CASCADE;

COMMIT;
