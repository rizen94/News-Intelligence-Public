-- Migration 256: pipeline_status backfill is operator-run (v10.1)
-- Use: PYTHONPATH=api python api/scripts/backfill_pipeline_status.py

BEGIN;
DO $$ BEGIN RAISE NOTICE '256: run api/scripts/backfill_pipeline_status.py for pipeline_status backfill'; END $$;
COMMIT;
