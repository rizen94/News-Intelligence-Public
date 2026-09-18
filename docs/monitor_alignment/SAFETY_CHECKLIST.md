# Monitor alignment — safety checklist

Pre/post deploy for terminology SSOT and rename passes.

## Prod-critical paths

- [ ] `AutomationManager` worker loop — no double-enqueue regression
- [ ] `PipelineController._replan` — stall_yield still yields truly stuck phases
- [ ] `persist_automation_run_history` — worker pool; falls back to `pending_db_writes`
- [ ] PgBouncer `:6432` for apps; migrations/admin on `:5432` only
- [ ] `PIPELINE_QUIET_HOURS_DISABLED` and gate envs unchanged unintentionally

## Unit tests (must pass)

```bash
PYTHONPATH=api python3 -m pytest \
  tests/unit/test_monitor_run_vocabulary.py \
  tests/unit/test_phase_batch_run_history.py \
  tests/unit/test_pipeline_phase_health.py \
  tests/unit/test_pipeline_schedule_service.py \
  -q
```

## API smoke

```bash
curl -sf http://127.0.0.1:8000/api/ping
curl -sf "http://127.0.0.1:8000/api/system_monitoring/processing_progress?use_backlog_snapshot=true" \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print('schema', d.get('monitor_schema_version')); print('phases', len(d.get('phase_dashboard',[])))"
curl -sf http://127.0.0.1:8000/api/system_monitoring/monitoring/overview | head -c 200
```

## DB verification (admin port)

```sql
SELECT phase_name, finished_at, metadata->>'status' AS status,
       metadata->>'round_processed' AS rp, metadata->>'scheduler_path' AS path
FROM automation_run_history
WHERE finished_at > NOW() - INTERVAL '1 hour'
  AND metadata->>'status' = 'batch_round'
ORDER BY finished_at DESC LIMIT 10;
```

## Soak criteria (30 min post-deploy)

- [ ] Unified and entity_profile show activity **and** `batch_round` rows with `scheduler_path=automation_manager`
- [ ] Pulse `runs_1h` increments for active drain phases within the hour
- [ ] `pending_records` decreases when `rows_processed > 0` (may lag one cache TTL ~90s)
- [ ] No spike in `stall_yield` for in-flight drains with activity feed entry

## Rollback

- Rsync previous `automation_manager.py`, `monitor_run_vocabulary.py`, `phase_batch_run_history.py`, `processing_progress.py`
- `sudo systemctl restart news-intelligence-api-public`
