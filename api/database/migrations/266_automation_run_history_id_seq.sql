-- Migration 266: Restore IDENTITY/sequence on infrastructure.automation_run_history.id
--
-- Migration 230 copied the table with LIKE ... INCLUDING ALL then DROP public.automation_run_history,
-- which dropped the serial sequence. INSERTs that omit id then fail:
--   null value in column "id" of relation "automation_run_history" violates not-null constraint
-- That emptied Grafana ni_automation_runs (24h) and Monitor pulse run counts since ~2026-11-07.
--
-- Date: 2026-11-12

BEGIN;

CREATE SEQUENCE IF NOT EXISTS infrastructure.automation_run_history_id_seq;

SELECT setval(
  'infrastructure.automation_run_history_id_seq',
  GREATEST(
    (SELECT COALESCE(MAX(id), 1) FROM infrastructure.automation_run_history),
    1
  )
);

ALTER TABLE infrastructure.automation_run_history
  ALTER COLUMN id SET DEFAULT nextval('infrastructure.automation_run_history_id_seq');

ALTER SEQUENCE infrastructure.automation_run_history_id_seq
  OWNED BY infrastructure.automation_run_history.id;

COMMIT;
