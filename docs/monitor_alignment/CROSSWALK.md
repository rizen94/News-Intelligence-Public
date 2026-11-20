# Monitor alignment crosswalk (NI ↔ Homelab)

Maps **who writes**, **who reads**, and **which homelab services** participate. Use with `docs/OPERATING_PRINCIPLES.md` §2.

---

## Surfaces

| Surface | Host | Role |
|---------|------|------|
| **Monitor UI** | Widow API + web | Live health, phase pulse, run-now, pool chips |
| **Prometheus scrape** | Widow `GET /api/system_monitoring/prometheus` | `ni_*` text exposition (cached) |
| **Grafana NI Ops** | PopOS Homelab (`uid=ni-ops`) | History: queues, RSS, DB growth, automation rates |
| **Alertmanager / rules** | PopOS | `api/monitoring/grafana/alerts-embeddings-host.yaml` + (planned) spine silent / metrics stale |

Import steps: `api/monitoring/grafana/README.md`.

---

## Data SSOT crosswalk

| Concern | Primary store | Writer(s) | Readers |
|---------|---------------|-----------|---------|
| Phase pending counts | `infrastructure.automation_state` (`monitor_backlog_snapshot`) | `monitor_backlog_snapshot_service` (refresh on drain + scheduled) | `backlog_metrics` (prefer snapshot), Monitor, Prometheus (target: snapshot not COUNT-on-scrape) |
| Snapshot history | `intelligence.monitor_backlog_snapshot_history` | snapshot service | Grafana trends (when wired) |
| Run history | `infrastructure.automation_run_history` | phase completion, cron heartbeat | `backlog_status`, `process_run_summary`, Grafana |
| Pool pressure | `public.db_pool_pressure_advisory` | API pool advisory | Monitor `db_pressure`, admission |
| Spine health (MVP tables) | `pipeline.spine_health`, `pipeline.pipeline_metrics` | **`metrics_materializer`** (not shipped) | Monitor v2 product lane (planned) |
| Embeddings host | Prometheus `ni_embeddings_*` | API metrics service | Grafana alerts YAML |

**Gap (repair plan P0):** Prometheus still often hits **live COUNT** when snapshot/cache cold → empty `ni_pipeline_backlog_total` under pool pressure.

---

## Homelab services (read-only for agents)

| Service | Access | Use for NI |
|---------|--------|------------|
| **postgres-mcp** | `http://127.0.0.1:18090/sse` | Read-only Widow `news_intel` — spine SQL, golden trace |
| **homelab-env-manager** | `hem_*` | Ports, compose reconcile — **not** NI deploy |
| **unified-search** | `unified_search` | Vault + MemPalace + allowlisted docs |
| **obsidian-vault** | `vault_*` | Handoffs, operator notes |
| **Prometheus/Grafana** | PopOS LAN | Dashboard import, alert rules — manual apply after JSON change |
| **Ollama** | `:11434` PopOS / Widow routing | Inference capacity — not metrics SSOT |
| **ntfy / fleet-notify** | (optional) | Future: spine silent alerts |

**Not used by default in coding profile:** `crawl4ai`, `scrapy`, `curl-impersonate` — enable from full `mcp-stack.json` when scraping.

Homelab boundary: `HomeLab-AI-Stack/docs/NEWS_INTELLIGENCE_INTEGRATION.md`.

---

## Agent checklist (monitoring ticket)

1. Name the **SSOT** (snapshot vs run history vs table COUNT).
2. Change **writers** first; then Prometheus/Monitor/Grafana readers.
3. After JSON dashboard change: note **manual Grafana import** on PopOS.
4. Do not claim product fixed from Grafana alone — golden trace if reader in scope.

---

## Related

- `docs/MONITOR_REPORTING_AND_METRICS.md`
- `docs/AVAILABLE_SERVICES_AND_MCP.md`
- `docs/NI_REPAIR_PLAN.md` § Observability