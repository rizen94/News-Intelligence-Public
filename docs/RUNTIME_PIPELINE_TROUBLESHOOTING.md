# Runtime pipeline troubleshooting (Widow)

**Audience:** Operators and **coding agents fixing NI runtime** — not in-app LLM workers, not homelab Life OS.  
**Last updated:** 2026-11-10  
**Live host:** Widow `192.168.93.101` — API on `127.0.0.1:8000` (not exposed on LAN unless tunneled).

Use this doc **before** vault handoffs or MemPalace search for schema/pipeline claims. Canonical behavior is in **repo docs + code + postgres-mcp**.

### Agent triage order (Cline Plan & Act)

1. This doc **§2** (evidence ladder)  
2. `./scripts/repomix_pack_ni.sh`  
3. `rg` / `grep_repomix_output` for phase or error string (symbol map §1 below)  
3b. **Call paths** — graphify MCP or `./scripts/graphify_ni_pipeline_slice.sh` + `graphify explain` ([GRAPHIFY_PIPELINE_SLICE.md](GRAPHIFY_PIPELINE_SLICE.md))  
4. **postgres-mcp** — SQL from §2, bounded  
5. Code change / deploy only after 1–4  

Same order in **`.clinerules/ni-agent.md`**.

---

## 1. Repomix-first navigation (code)

Packed API tree (fast symbol search without loading megabyte files):

```bash
cd ~/Documents/projects/news_intelligence   # or Widow /opt/news-intelligence
./scripts/repomix_pack_ni.sh                  # writes repomix-output.xml (~4MB)
rg -n "FUNCTION_OR_CLASS" repomix-output.xml  # quick scan
# MCP: grep_repomix_output (homelab repomix MCP server)
```

**When to refresh the pack:** after deploy, or any session where you grep and get stale paths. Pack is **api/** only (see `repomix.config.json`).

### Pipeline symbol map (grep these first)

| Symptom area | Repomix / rg target | Primary file |
|--------------|---------------------|--------------|
| Phases not running, queue, schedules | `PipelineController`, `reconcile_and_enqueue`, `_execute_` | `api/services/automation_manager.py` |
| What “pending” means | `BATCH_SIZE_PER_TASK`, `_count_`, `backlog_metrics` | `api/services/backlog_metrics.py` |
| Admission / flat scheduler | `pick_next_phases`, `pipeline_admission` | `api/services/pipeline_controller.py`, `api/shared/pipeline_admission.py` |
| Domain schemas | `get_pipeline_active_domain_keys`, `validate_schema_name` | `api/shared/domain_registry.py` |
| Article lane SQL errors | `sql_article_signal_full_lane`, `quality_tier` | `api/shared/article_signal_gate.py` |
| Ollama host/model | `_execution_lane_for_kind`, `llm_service` | `api/shared/services/ollama_model_policy.py`, `api/shared/services/llm_service.py` |
| Monitor / health | `system_monitoring`, `degraded_reasons` | `api/routes/system_monitoring.py` (under routes tree) |
| RSS intake | `collect_rss_feeds` | `api/collectors/rss_collector.py` |
| Heartbeat writes | `pipeline_phase_heartbeats` | grep callers in `api/services/` |

**Deep narrative (no code dump):** [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md)  
**Operator checklist:** [PIPELINE_OPERATIONS_WIDOW.md](PIPELINE_OPERATIONS_WIDOW.md)  
**DB reference:** [DATABASE.md](DATABASE.md)  
**Monitor semantics:** [MONITOR_REPORTING_AND_METRICS.md](MONITOR_REPORTING_AND_METRICS.md)

---

## 2. Evidence ladder (prove it on Widow)

Run on Widow (SSH) or via **postgres-mcp** against `news_intel` (Widow, not Homelab `:15432`).

| Step | Check | Pass criterion |
|------|--------|----------------|
| A | Services | `systemctl is-active news-intelligence-api-public.service newsplatform-secondary.service` → `active` |
| B | API health | `curl -sS --max-time 15 http://127.0.0.1:8000/api/system_monitoring/health` → `status` not `degraded` for DB (see §4) |
| C | Schemas | `list_schemas` — pipeline monitoring in **`pipeline.*`**; domain articles in **`politics`**, **`finance`**, etc. |
| D | Phase freshness | `SELECT phase_name, last_run_at, last_success FROM pipeline.pipeline_phase_heartbeats ORDER BY last_run_at DESC LIMIT 10` — **last_run_at within hours**, not days old |
| E | Intake | Per domain: `SELECT COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours'), MAX(created_at) FROM {schema}.articles` |
| F | Run history | `SELECT * FROM infrastructure.automation_run_history ORDER BY …` (use `get_object_details` first; column names vary by migration) |

**Never** conclude from migration filenames alone or from Obsidian triage notes.

---

## 3. Symptom → doc → code (quick matrix)

| Symptom | Read first | Repomix / open | SQL hint |
|---------|------------|----------------|----------|
| Health `database: connection timeout` | [PGBOUNCER_AND_CONNECTION_BUDGET.md](PGBOUNCER_AND_CONNECTION_BUDGET.md) | `get_db_connection_context`, pool stats in logs | Check `DB_HOST=127.0.0.1` `DB_PORT=6432`; journal for `pool timeout` / `uncommitted tx` |
| Phases stale (heartbeats days old) | PIPELINE_AND_AUTOMATION § Scheduling | `AutomationManager`, `PipelineController` | Heartbeats query (§2D); check API was running, not stuck `deactivating` |
| No new articles | PIPELINE_OPERATIONS § Quiet windows | `collect_rss_feeds`, `pipeline_schedule_service` | Article counts §2E; RSS quiet is **expected** weekday daytime |
| `InvalidTextRepresentation` `tier_1` on `quality_tier` | This doc §5 | `article_signal_gate.py` | `quality_tier` is **smallint** `1/2/3`, not `'tier_1'` strings |
| Log spam `rejecting domain 'general'` | DOMAIN_EXTENSION_TEMPLATE | `domain_registry`, `validate_schema_name` | `SELECT domain_key, is_active FROM public.domains` — deactivate or fix schema |
| Ollama / GPU deferrals | MONITOR_REPORTING_AND_METRICS | `llm_service`, circuit breakers | Health JSON `circuit_breakers`; reset per TROUBLESHOOTING |
| Backlog UI vs Grafana disagree | MONITOR_REPORTING_AND_METRICS | `backlog_metrics`, prometheus routes | Compare live SQL vs scraped metrics |

---

## 4. Widow health and services (copy/paste)

```bash
# On Widow
systemctl is-active news-intelligence-api-public.service newsplatform-secondary.service
curl -sS --max-time 15 http://127.0.0.1:8000/api/system_monitoring/health | python3 -m json.tool | head -40

# If API hung stopping (deactivating / stop-sigterm): see TROUBLESHOOTING → API restart
# journal tail
journalctl -u news-intelligence-api-public.service -n 50 --no-pager | grep -iE 'ERROR|pool|tier_1|phase'
```

Deploy path: `/opt/news-intelligence` — compare `BUILD_INFO` / git SHA to dev tree after `./scripts/deploy_to_widow.sh`.

---

## 5. Known failure modes (2026-11)

### 5.1 `quality_tier = 'tier_1'` SQL bug

- **Cause:** `articles.quality_tier` is `smallint`; signal-first SQL compared to string tiers.
- **Symptom:** Logs: `invalid input syntax for type smallint: "tier_1"`; proactive detection / assembly loops fail; pool churn (`uncommitted tx — dropping`).
- **Fix:** `api/shared/article_signal_gate.py` — compare to `1` and `2`, not `'tier_1'` / `'tier_2'`.
- **Verify:** No `tier_1` errors in journal after API restart; heartbeats begin updating.

### 5.2 Connection pool exhaustion

- **Symptom:** `Database ui pool timeout`, `worker pool exhausted`, health `degraded` DB.
- **Often coupled with:** repeated SQL errors (§5.1) or connection leaks.
- **Mitigate:** Fix throwing queries; restart API; review [PGBOUNCER_AND_CONNECTION_BUDGET.md](PGBOUNCER_AND_CONNECTION_BUDGET.md).

### 5.3 Inactive `general` domain in `public.domains`

- **Symptom:** ERROR lines rejecting `general_news` schema (not on whitelist).
- **Data:** `general` may be `is_active = false` but still merged from YAML — some code paths iterate all registry entries.
- **Mitigate:** Ensure callers use `get_active_domain_keys()` / pipeline iterators; optional DB cleanup of stale row.

### 5.4 Stale `pipeline.pipeline_phase_heartbeats`

- If **last_run_at** is days behind while API is `active`, automation is not completing phases or not writing heartbeats — trace `PipelineController` / worker logs, not MemPalace diaries.

---

## 6. What not to use for runtime diagnosis

| Source | Why |
|--------|-----|
| MemPalace `diary` / investigator sessions | Hypotheses and superseded schema narratives |
| Obsidian `00_Inbox` triage notes | Point-in-time debugging, not SoT |
| `.clinerules` SQL cheats mentioning `public.pipeline_*` without `list_schemas` | May predate `pipeline` schema consolidation |
| Generated `ONBOARDING_CONTEXT.md` | Regenerate via `scripts/context_pack.py` if used at all |

For **coding-agent** hygiene (handoffs, commits), handle in homelab — not here.

---

## 7. Related scripts (repo)

| Script | Purpose |
|--------|---------|
| `./scripts/repomix_pack_ni.sh` | Refresh `repomix-output.xml` |
| `scripts/verify_pipeline_db_alignment.py` | DB vs code alignment |
| `scripts/poll_extracted_events_and_pipeline.py` | Pipeline activity poll |
| `scripts/full_system_status_check.py` | Broad status (run on Widow with env) |

---

## 8. Index

Parent index: [DOCS_INDEX.md](DOCS_INDEX.md) · General issues: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
