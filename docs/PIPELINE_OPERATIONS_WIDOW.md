# Pipeline Operations — Widow (June 2026)

**Purpose:** Operator checklist for the full News Intelligence data pipeline on **Widow** — schedulers, phases, and known split-host patterns after PopOS→Widow migration.

**Deep reference:** [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) · [WIDOW_DB_ADJACENT_CRON.md](WIDOW_DB_ADJACENT_CRON.md) · `api/services/automation_manager.py`

---

## End-to-end flow (intake → product)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 0 — INGEST (Widow, outside AutomationManager or inside collection_cycle) │
├─────────────────────────────────────────────────────────────────────────────┤
│ newsplatform-secondary.service  →  collect_rss_feeds  →  {domain}.articles │
│   (10 min; quiet window weekday daytime)                                      │
│ cron */15 run_widow_db_adjacent.py  →  context_sync*, entity_profile_sync*, │
│                                         pending_db_flush                    │
│ AutomationManager: collection_cycle  →  enrichment + docs + queue drain     │
│ AutomationManager: content_enrichment  →  full-text (Trafilatura)           │
│ AutomationManager: document_processing  →  PDFs                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 1 — FOUNDATION (AutomationManager on Widow API)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ context_sync*           articles → intelligence.contexts                     │
│ entity_profile_sync*    canonical entity maps                               │
│ metadata_enrichment     article metadata                                    │
│ ml_processing           ML batch passes                                     │
│ entity_extraction       article_entities                                    │
│ entity_profile_build    entity_profiles                                     │
│ embeddings_worker       vector embeddings                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 2 — EXTRACTION & EVENTS                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ claim_extraction → claims_to_facts → extracted_claims_dedupe                  │
│ event_tracking → event_coherence_review → investigation_report_refresh      │
│ event_extraction → event_deduplication → story_continuation                 │
│ legislative_references · cross_domain_synthesis · pattern_recognition       │
│ quality_scoring · sentiment_analysis · topic_clustering                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 3 — STORYLINES & INTELLIGENCE PRODUCTS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ storyline_discovery → storyline_processing → storyline_automation           │
│ storyline_enrichment → content_refinement_queue → narrative finisher (5090) │
│ storyline_synthesis · story_enhancement · timeline_generation               │
│ editorial_* · daily_briefing_synthesis · digest_generation · watchlist_alerts│
│ arc_report_generation · rag_enhancement · entity_dossier_compile              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 4 — MAINTENANCE & NIGHTLY                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ nightly_enrichment_context  (02:00–07:00 local unified drain)               │
│ cache_cleanup · data_cleanup · health_check · longitudinal_matview_refresh  │
│ macro_series_refresh · sanctions_refresh · external_events_sync             │
└─────────────────────────────────────────────────────────────────────────────┘
```

\* **`context_sync`, `entity_profile_sync`, `pending_db_flush`** run via **cron** on Widow and must be **disabled** in AutomationManager (`AUTOMATION_DISABLED_SCHEDULES`) to avoid duplicate work.

---

## Schedulers on Widow (what must be running)

| Scheduler | Location | Schedule | Role |
|-----------|----------|----------|------|
| **API + AutomationManager** | `uvicorn` / `news-intelligence-api-public.service` | Always on | All phases except disabled list |
| **newsplatform-secondary** | systemd | Every 10 min | RSS when not in quiet window |
| **widow-db-adjacent** | `/etc/cron.d/widow-db-adjacent` | `*/15 * * * *` | context_sync, entity_profile_sync, pending_db_flush |
| **log archive** | user crontab | Daily 05:00 | `archive_logs_to_nas.sh` |
| **DB backup** | user crontab | Sun 04:30 | `db_backup_weekly_retained.sh` |
| **nightly_enrichment_context** | AutomationManager | 02:00–07:00 EST window | Unified enrichment + context drain |

### Required `.env` on Widow (`/opt/news-intelligence/.env`)

```bash
# RSS on secondary worker — skip duplicate fetch in collection_cycle
AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE=true

# Cron runs these on Widow — disable in AutomationManager
AUTOMATION_DISABLED_SCHEDULES=context_sync,entity_profile_sync,pending_db_flush

# GTX 1080 8GB — lower parallelism (defaults were sized for 5090)
AUTOMATION_MAX_CONCURRENT_TASKS=6
# Align with OLLAMA_CONCURRENCY in llm_service.py (code default 6); tune down on 1080 if needed
MAX_CONCURRENT_OLLAMA_TASKS=6
# Backlog metrics cache for Monitor pending columns (code default 90s)
BACKLOG_CACHE_TTL_SECONDS=90
# 70B narrative finisher concurrency (content_refinement_queue_service)
NARRATIVE_FINISHER_MAX_INFLIGHT=1

# DB via PgBouncer
DB_HOST=127.0.0.1
DB_PORT=6432

# Ollama — Widow is primary (CPU + GPU lanes on local :11434); PopOS 5090 only for heavy models (70B finisher)
OLLAMA_HOST=http://localhost:11434
OLLAMA_POP_OS_HOST=http://192.168.93.99:11434
# Leave dual-host OFF unless you intentionally split lanes across two Ollama servers (not the default NI policy).
OLLAMA_DUAL_HOST_ROUTING_ENABLED=false
OLLAMA_MODEL_PRIMARY=llama3.1:8b
OLLAMA_MODEL_SECONDARY=llama3.1:8b
OLLAMA_MODEL_EXTRACTION=qwen2.5:7b
```

---

## AutomationManager phases (complete list)

Source: `automation_manager.py` → `self.schedules` (phase 0–4 + maintenance).

| Phase | Task name | Typical interval |
|-------|-----------|------------------|
| 0 | `collection_cycle` | ~2h (orchestrator config) |
| 0 | `nightly_enrichment_context` | 60s (active in nightly window) |
| 0 | `document_processing` | 10 min |
| 0 | `content_enrichment` | 5 min |
| 1 | `context_sync` | 15 min *(cron on Widow)* |
| 1 | `entity_profile_sync` | 6h *(cron on Widow)* |
| 1 | `entity_profile_build` | 15 min |
| 1 | `metadata_enrichment` | varies |
| 2 | `claim_extraction` | 30 min |
| 2 | `legislative_references` | 1h |
| 2 | `claims_to_facts` | 1h |
| 2 | `claim_subject_gap_refresh` | 6h |
| 2 | `extracted_claims_dedupe` | 12h |
| 2 | `event_tracking` | 15 min |
| 2 | `cross_domain_synthesis` | 30 min |
| 2 | `pattern_recognition` | 2h |
| 2 | `embeddings_worker` | 1h |
| 2 | `macro_series_refresh` | varies |
| 2 | `external_events_sync` | varies |
| 2 | `sanctions_refresh` | varies |
| 3 | `event_coherence_review` | 2h |
| 3 | `investigation_report_refresh` | 2h |
| 3 | `ml_processing` | varies |
| 3 | `entity_extraction` | parallel group |
| 3 | `quality_scoring` | parallel group |
| 3 | `sentiment_analysis` | parallel group |
| 3 | `topic_clustering` | varies |
| 3+ | `storyline_*`, `editorial_*`, `event_*`, `rag_*`, … | see code |
| — | `health_check` | manual / monitor |
| — | `pending_db_flush` | *(cron on Widow)* |

---

## Quiet windows (expected “no RSS” behavior)

Both **RSS secondary worker** and **db-adjacent cron** honor `pipeline_schedule_service` quiet windows:

- **Weekday daytime:** RSS/context often **skipped** (logged as `pipeline quiet window`)
- **Active windows:** weekday 07:00–16:00 and nightly 00:00–07:00 local (see `api/services/pipeline_schedule_service.py`)

This is **not** a failure — intake resumes in the active window.

---

## Orchestrator

- **Config:** `api/config/orchestrator_governance.yaml`
- **Coordinator:** `api/services/orchestrator_coordinator.py` — can `request_phase` based on governance
- **Dashboard API:** `/api/orchestrator/dashboard` (Monitor UI)

Collection interval and throttle thresholds are driven by orchestrator governance + `COLLECTION_THROTTLE_*` env vars.

---

## Boot resilience (systemd)

Production API **must** run via systemd — not manual nohup. See **[WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md)**.

```bash
# Install / enable (once)
cd /opt/news-intelligence && ./scripts/setup_widow_boot_stack.sh
sudo systemctl enable --now news-intelligence.target

# After reboot
/opt/news-intelligence/scripts/verify_widow_boot.sh
curl -s http://127.0.0.1:8000/api/system_monitoring/startup/readiness | jq .ready
```

---

## Operator commands (Widow)

```bash
# Readiness + health
curl -s http://127.0.0.1:8000/api/system_monitoring/startup/readiness | jq .
curl -s http://127.0.0.1:8000/api/system_monitoring/health | jq .
curl -s http://127.0.0.1:8000/api/system_monitoring/automation/status | jq '.data | {startup_ready, workers: .active_workers, window: .pipeline_schedule.active_window}'

# Manually queue a phase (Monitor API)
curl -X POST http://127.0.0.1:8000/api/system_monitoring/monitoring/trigger_phase \
  -H 'Content-Type: application/json' \
  -d '{"phase":"content_enrichment"}'

# Restart API after .env changes
sudo systemctl restart news-intelligence-api-public
# or: cd /opt/news-intelligence && bash scripts/restart_api_with_db.sh

# RSS worker
sudo systemctl status newsplatform-secondary

# DB-adjacent cron log
tail -f /opt/news-intelligence/logs/widow_db_adjacent.log

# Ollama models (1080 — one large model at a time)
ollama list
```

---

## Interruptions found (June 2026 audit) — remediated

| Issue | Evidence | Fix applied |
|-------|----------|-------------|
| **DB pool exhausted** | 648k+ errors in `/tmp/uvicorn_start.log` | Restart API; `DB_POOL_UI/WORKER_MAX=24`; `AUTOMATION_MAX_CONCURRENT_TASKS=6` |
| **Missing automation env** | No `AUTOMATION_SKIP_RSS` / `DISABLED_SCHEDULES` | Added Widow-unified settings to `.env` |
| **Ollama partial** | Only `llama3.1:8b` pulled | Pull `qwen2.5:7b`, `nomic-embed-text` in progress |
| **API not systemd** | Manual nohup since Jun 5 | **Fixed Jun 6:** `setup_widow_boot_stack.sh` + `news-intelligence-api-public` enabled |
| **Stale ML phases** | `topic_clustering`, `ml_processing` last run Jun 2 | Lower concurrency + restart; trigger via Monitor or wait for workload-driven scheduling |

---

## Bulk catch-up (one-time historical drain)

Use when steady automation cannot close a large backlog (false pass markers reconciled, pool healthy).

**Warning:** `--force` bypasses quiet-hour gating. Run off-peak; monitor pool and NRI watermark lag.

```bash
cd /opt/news-intelligence

# 1. Baseline
DEBUG_RUN_ID=baseline-before PYTHONPATH=api python3 api/scripts/diagnose_pipeline_pathways.py \
  | tee docs/pipeline_repair/baseline-$(date +%Y%m%d)-before.json

# 2. Reconcile false pass markers (dry-run first)
PYTHONPATH=api python3 api/scripts/reconcile_false_pass_markers.py --dry-run --phase all
PYTHONPATH=api python3 api/scripts/reconcile_false_pass_markers.py --phase all --limit 50000

# 3. Apply migration 235 (phase heartbeats) if not applied
PYTHONPATH=api python3 api/scripts/apply_migrations.py  # or psql -f api/database/migrations/235_*.sql

# 3b. Pause competing NI/NRI work (RSS, cron sync, AutomationManager phases, NRI mention resolver)
bash scripts/pause_for_bulk_catchup.sh
sudo systemctl restart news-intelligence-api-public

# 4. Bulk catch-up (checkpoint: data/bulk_catchup_state.json)
# Script auto-loads .env (DB_HOST=127.0.0.1 DB_PORT=6432). Use .venv/bin/python on Widow.
# bulk_catchup.py also writes data/bulk_catchup_competition_pause.json if not already set.
PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup.py --dry-run
# Widow 1080 only (slow, avoid 503 — keep parallel ≤2):
BULK_ENTITY_PARALLEL=2 OLLAMA_GPU_CONCURRENCY=2 \
  PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup.py --force --no-use-popos-gpu

# PopOS RTX 5090 offload (recommended for entity extraction throughput):
BULK_ENTITY_EXTRACTION_PER_DOMAIN=500 BULK_ENTITY_PARALLEL=4 BULK_NRI_MENTION_BATCH_PAUSE=3 \
  BULK_EXTRACTION_MODEL=llama3.1:8b \
  PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup.py --force --use-popos-gpu
# Optional: on PopOS run `ollama pull qwen2.5:7b` then BULK_EXTRACTION_MODEL=qwen2.5:7b

# 5. Embeddings + storylines (after entity/claim phases)
PYTHONPATH=api python3 api/scripts/backfill_embedding_chunks.py --limit 200 --loops 50
PYTHONPATH=api python3 api/scripts/run_storyline_discovery_catchup.py

# 6. After snapshot
DEBUG_RUN_ID=baseline-after PYTHONPATH=api python3 api/scripts/diagnose_pipeline_pathways.py \
  | tee docs/pipeline_repair/baseline-$(date +%Y%m%d)-after.json

# 7. Resume normal NI/NRI scheduling
bash scripts/resume_after_bulk_catchup.sh
sudo systemctl restart news-intelligence-api-public

# Monitor in another terminal:
scripts/bulk_status.sh
scripts/bulk_status.sh --watch 60   # refresh every 60s
```

Env tunables: `BULK_CONTEXT_SYNC_LIMIT`, `BULK_ENTITY_EXTRACTION_PER_DOMAIN`, `BULK_CLAIM_LIMIT`, `BULK_NRI_MENTION_BATCH_PAUSE`, `BULK_STEADY_STATE_FLOOR` (default 50).

Steady-state defaults (post bulk): `ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN=40`, nightly `entity_extraction:12` in `NIGHTLY_SEQUENTIAL_PHASE_LOOP_CAPS`.

### Topic clustering catch-up (migrations 242–243)

Automation now writes **`topic_clusters` only** (legacy `topics` is read-only). Apply migrations, then drain backlog:

```bash
cd /opt/news-intelligence && set -a && . .env && set +a

# Migrations: trgm indexes + mv_topic_index
PYTHONPATH=api .venv/bin/python3 api/scripts/apply_migrations.py

# Recommended catch-up env (also in .env):
# TOPIC_CLUSTERING_BATCH_SIZE=50 TOPIC_CLUSTERING_CONCURRENCY=5 TOPIC_FAST_MATCH_MIN_SCORE=0.62

PYTHONPATH=api .venv/bin/python3 api/scripts/catchup_topic_clustering.py --dry-run
PYTHONPATH=api .venv/bin/python3 api/scripts/catchup_topic_clustering.py --batch-size 50 --concurrency 5

# Weekly (cron): refresh matview + auto-merge high-confidence duplicates
PYTHONPATH=api .venv/bin/python3 api/scripts/refresh_topic_index_matviews.py
PYTHONPATH=api .venv/bin/python3 api/scripts/run_topic_cluster_merge_batch.py --dry-run
PYTHONPATH=api .venv/bin/python3 api/scripts/run_topic_cluster_merge_batch.py --apply
```

Verify: pending pass-marker backlog trending below 2k; no new rows in `{schema}.topics` after deploy timestamp.

---

## Related

- [DATABASE_DATA_QUALITY_AUDIT_2026-06.md](DATABASE_DATA_QUALITY_AUDIT_2026-06.md) — denormalized column repair runbook
- [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md) — reboot / systemd runbook
- [pipeline_repair/ROOT_CAUSE_REPORT.md](pipeline_repair/ROOT_CAUSE_REPORT.md) — June 2026 audit
- [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) — hosts & GPU
- HomeLab [PUBLIC_HTTPS_ROUTING.md](../../HomeLab-AI-Stack/docs/PUBLIC_HTTPS_ROUTING.md)
