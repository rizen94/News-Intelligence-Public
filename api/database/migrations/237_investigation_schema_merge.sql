-- Investigation schema unification: nri.* → intelligence.investigation_*
-- Apply during maintenance window. Set USE_INVESTIGATION_PREFIXED_TABLES=true after cutover.
-- Rollback: pg_restore from pre-cutover dump.

BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.investigation_watermarks (
    LIKE nri.watermarks INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_resolved_mentions (
    LIKE nri.resolved_mentions INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_parked_resolution (
    LIKE nri.parked_resolution INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_entity_bridge (
    LIKE nri.entity_bridge INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_provisional_mints (
    LIKE nri.provisional_mints INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_ftm_entity_cache (
    LIKE nri.ftm_entity_cache INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_loop_run (
    LIKE nri.loop_run INCLUDING ALL
);

INSERT INTO intelligence.investigation_watermarks
SELECT * FROM nri.watermarks
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_resolved_mentions
SELECT * FROM nri.resolved_mentions
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_parked_resolution
SELECT * FROM nri.parked_resolution
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_entity_bridge
SELECT * FROM nri.entity_bridge
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_provisional_mints
SELECT * FROM nri.provisional_mints
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_ftm_entity_cache
SELECT * FROM nri.ftm_entity_cache
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_loop_run
SELECT * FROM nri.loop_run
ON CONFLICT DO NOTHING;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA intelligence TO newsapp;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intelligence TO newsapp;

-- nri.* remain physical tables until bake; homelab MCP can read intelligence.investigation_* directly.
-- Do not CREATE VIEW over nri.* — those names are tables and will abort the transaction.

COMMIT;
