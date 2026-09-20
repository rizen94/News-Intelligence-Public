# Upgrade to News Intelligence 10.1

Operator runbook for the `release/10.1` branch cutover on Widow.

## Prerequisites

- Branch: `release/10.1` merged to `main`, tag `v10.1.0`
- Dev workspace on Widow: `/home/pete/Documents/projects/News Intelligence`
- Production path: `/opt/news-intelligence`
- Database: `news_intel` on Widow `:5432` (migrations); apps use PgBouncer `:6432`

## Success criterion

`intake_processing_ratio.py --json` shows **net_growth ≤ 0** for **7 consecutive days** after cutover.

## Migration batch (249–260)

Run on Widow with direct Postgres (`DB_MAINTENANCE_PORT=5432`):

| # | File | Purpose |
|---|------|---------|
| 249 | `249_feature_registry_overrides.sql` | Optional runtime feature overrides |
| 250 | `250_pipeline_admission_config.sql` | Adaptive signal threshold persistence |
| 251 | `251_pipeline_status.sql` | Narrow pipeline eligibility table |
| 252 | `252_content_enrichment_queue.sql` | Per-domain enrichment queues |
| 253 | `253_unified_intake_queue.sql` | Per-domain unified intake queues |
| 254 | `254_spine_tail_queue.sql` | Global spine SQL tail queue |
| 255 | `255_entity_relationships_co_occurrence.sql` | Co-mention count aggregation columns |
| 256 | `256_pipeline_status_backfill_stub.sql` | Operator note; run `backfill_pipeline_status.py` |

```bash
cd /opt/news-intelligence
PYTHONPATH=api python api/scripts/run_migrations.py  # or project migration runner
```

## Environment changes (v10.1 defaults)

```bash
# Admission control (YAML in orchestrator_governance.yaml also applies)
ARTICLE_SIGNAL_ENABLED=true
RSS_FEED_SILENCE_ENABLED=true
RSS_FEED_SILENCE_DRY_RUN=true   # set false after one-week dry-run review

# Conductors (four-loop scheduling)
SPINE_PIPELINE_MODE=ordered
ASSEMBLY_PIPELINE_MODE=ordered

# Intake fusion (exclusive)
UNIFIED_INTAKE_EXTRACTION_ENABLED=true
LEGACY_INTAKE_EXTRACTION_ENABLED=false

# Steady-state model (after verify_intake_fusion_quality.py passes)
BULK_EXTRACTION_MODEL=qwen2.5:14b-instruct
```

## Deploy sequence

1. Stop API: `sudo systemctl stop news-intelligence-api-public.service`
2. Sync tree: rsync or git pull `v10.1.0` to `/opt/news-intelligence`
3. Run migrations 249–255
4. Run backfill scripts if documented for your backlog size
5. Start API: `sudo systemctl start news-intelligence-api-public.service`
6. Verify: `curl -s http://127.0.0.1:8000/ | jq .data.version` → `10.1.0`
7. Monitor: `/api/system_monitoring/processing_progress` and `intake_processing_ratio.py`

## Rollback

1. `sudo systemctl stop news-intelligence-api-public.service`
2. Checkout previous tag on `/opt/news-intelligence`
3. **Do not** drop new tables without DBA review — v10.1 tables are additive
4. Set `LEGACY_INTAKE_EXTRACTION_ENABLED=true` and `UNIFIED_INTAKE_EXTRACTION_ENABLED=false` for intake rollback (loads `api/_archived/intake/` via `api/shared/legacy_intake_rollback.py`)
5. Set `ASSEMBLY_PIPELINE_MODE=legacy` to re-enable workload-driven retired assembly phases (handlers in `api/_archived/automation/retired_phase_handlers.py`)
6. Set `ARTICLE_SIGNAL_ENABLED=false` to disable admission gating
7. Restart API

## Archive layout (v10.1 prune)

| Path | Contents |
|------|----------|
| `api/_archived/intake/` | Legacy entity/event runners, ml_processing, metadata_enrichment |
| `api/_archived/automation/retired_phase_handlers.py` | POST_SPINE_RETIRED phase handlers |
| `api/_archived/services/` | relationship_extraction, NRI shim services |
| `api/_archived/scripts/` | Superseded catch-up scripts (use `drain_phase.py`) |
| `docs/_archive/agent_investigations_2026/` | Retired root investigation markdown |

## Feature registry

See [FEATURE_REGISTRY.md](FEATURE_REGISTRY.md). Search features:

```bash
PYTHONPATH=api python api/scripts/list_features.py --lifecycle incorporated
curl -s 'http://127.0.0.1:8000/api/system_monitoring/features' | jq .
```

## Verification checklist

- [ ] `python scripts/verify_single_source_of_truth.py`
- [ ] `PYTHONPATH=api python api/scripts/verify_v10_1_wiring.py`
- [ ] `PYTHONPATH=api python scripts/verify_orchestrator_pipeline_connectivity.py`
- [ ] `PYTHONPATH=api python api/scripts/intake_processing_ratio.py`
- [ ] `PYTHONPATH=api python api/scripts/verify_intake_fusion_quality.py`
- [ ] Monitor shows conductor run history with throughput keys
